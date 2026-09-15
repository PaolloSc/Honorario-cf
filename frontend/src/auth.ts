import NextAuth from "next-auth";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
import { NextResponse } from "next/server";
import { callbackUrlSeguro } from "@/lib/callback-url";

declare module "next-auth" {
  interface Session {
    accessToken?: string;
    // Quando o refresh do token Azure falha (refresh token revogado/expirado por
    // inatividade), a sessao next-auth continua valida por 30 dias e o usuario
    // segue "logado" — mas todo request para a API volta 401 "Token expirado".
    // Este campo deixa o front perceber e pedir novo login em vez de travar.
    error?: "RefreshAccessTokenError";
    // Codigo curto do motivo real da falha (ex. "invalid_grant"), so' para
    // diagnostico: sem ele a faixa de erro nao diz nada acionavel.
    errorCode?: string;
    expiresAt?: number;
    user: {
      id?: string;
      name?: string | null;
      email?: string | null;
      image?: string | null;
      role?: string;
    };
  }
}

/**
 * `exp` (epoch em segundos) de um JWT, sem validar assinatura — serve so' para
 * saber quando renovar. O backend valida o token de verdade.
 *
 * O app manda o *id_token* como Bearer, mas `account.expires_at` e' a validade do
 * *access_token*. Sao tokens diferentes: usar o exp errado faz o agendamento do
 * refresh divergir da expiracao real e a API responder 401 "Token expirado".
 */
function expDoJwt(jwtToken?: string | null): number | undefined {
  if (!jwtToken) return undefined;
  const payload = jwtToken.split(".")[1];
  if (!payload) return undefined;
  try {
    // atob, nao Buffer: este modulo tambem e' empacotado para o middleware, que
    // roda no Edge — la' Buffer nao existe e a leitura do exp falhava calada.
    const b64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const bin = atob(b64.padEnd(Math.ceil(b64.length / 4) * 4, "="));
    const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
    const exp = JSON.parse(new TextDecoder().decode(bytes))?.exp;
    return typeof exp === "number" ? exp : undefined;
  } catch {
    return undefined;
  }
}

// Renova com esta antecedencia do vencimento. Nao adianta ser generoso: o que
// garante token fresco na hora da chamada e' o garantirTokenValido() do cliente.
// Margem larga so' alarga a janela em que varias abas tentam renovar juntas.
const MARGEM_RENOVACAO_MS = 120_000;

type TokenJWT = Record<string, unknown>;

/**
 * Falha de renovacao NAO e' o mesmo que sessao morta. Corrida entre abas, blip de
 * rede ou refresh token ja' rotacionado pelo Entra sao transitorios: enquanto o
 * id_token atual ainda vale, seguimos com ele e tentamos de novo depois. Marcar a
 * sessao como expirada nesses casos foi o que pos a faixa vermelha na tela de
 * quem tinha acabado de entrar.
 */
function marcarSeVencido(
  token: TokenJWT,
  expiresAt: number | undefined,
  codigo: string,
): TokenJWT {
  const aindaVale = typeof expiresAt === "number" && Date.now() < expiresAt * 1000;
  if (aindaVale) return token;
  token.error = "RefreshAccessTokenError";
  token.errorCode = codigo;
  return token;
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    MicrosoftEntraID({
      clientId: process.env.AZURE_AD_CLIENT_ID!,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
      issuer: `https://login.microsoftonline.com/${process.env.AZURE_AD_TENANT_ID!}/v2.0`,
      authorization: {
        params: {
          scope: "openid profile email User.Read offline_access",
        },
      },
    }),
  ],
  callbacks: {
    authorized({ auth, request }) {
      const isLoggedIn = !!auth?.user;
      const path = request.nextUrl.pathname;
      if (path.startsWith("/login")) return true;
      if (isLoggedIn) return true;
      // Caminho relativo: o form/OAuth da Vercel perde a URL absoluta do preview.
      const login = request.nextUrl.clone();
      login.pathname = "/login";
      login.search = "";
      login.searchParams.set("callbackUrl", `${path}${request.nextUrl.search}` || "/");
      return NextResponse.redirect(login);
    },
    async jwt({ token, account }) {
      if (account) {
        token.accessToken = account.id_token;
        token.refreshToken = account.refresh_token;
        token.expiresAt = expDoJwt(account.id_token) ?? account.expires_at;
        delete token.error;
        delete token.errorCode;
        return token;
      }

      const expiresAt = typeof token.expiresAt === "number" ? token.expiresAt : undefined;
      if (
        token.accessToken &&
        expiresAt &&
        Date.now() < expiresAt * 1000 - MARGEM_RENOVACAO_MS
      ) {
        return token;
      }

      // O middleware cobre quase toda rota e dispara este callback a cada
      // requisicao, mas roda no Edge e nao persiste o cookie de forma confiavel.
      // Renovar ali queima o refresh token — que o Entra rotaciona e invalida no
      // primeiro uso — sem guardar o novo, e a requisicao seguinte levava
      // invalid_grant. A renovacao fica só com o Node (/api/auth/session), que
      // grava o resultado.
      if (process.env.NEXT_RUNTIME === "edge") return token;

      if (!token.refreshToken) {
        // Pode ser que o Entra nao devolva refresh token (offline_access sem
        // consentimento). Nao ha o que renovar, mas enquanto o id_token atual
        // valer o usuario continua trabalhando.
        return marcarSeVencido(token, expiresAt, "sem_refresh_token");
      }

      // Variavel faltando no ambiente vira client_secret="undefined" no corpo, e o
      // Azure responde invalid_client — indistinguivel de segredo expirado. Sem
      // esta checagem o diagnostico aponta para o lado errado.
      if (
        !process.env.AZURE_AD_TENANT_ID ||
        !process.env.AZURE_AD_CLIENT_ID ||
        !process.env.AZURE_AD_CLIENT_SECRET
      ) {
        console.error("[AUTH] Credenciais do Entra ausentes no ambiente");
        return marcarSeVencido(token, expiresAt, "config_ausente");
      }

      try {
        const url = `https://login.microsoftonline.com/${process.env.AZURE_AD_TENANT_ID}/oauth2/v2.0/token`;
        const body = new URLSearchParams({
          client_id: process.env.AZURE_AD_CLIENT_ID!,
          client_secret: process.env.AZURE_AD_CLIENT_SECRET!,
          grant_type: "refresh_token",
          refresh_token: token.refreshToken as string,
          scope: "openid profile email User.Read offline_access",
        });
        const res = await fetch(url, { method: "POST", body, headers: { "Content-Type": "application/x-www-form-urlencoded" } });
        const data = await res.json().catch(() => ({}));

        if (!res.ok || !data.id_token) {
          const codigo = data?.error ?? `http_${res.status}`;
          const descricao = String(data?.error_description ?? "");
          console.error("[AUTH] Falha ao renovar token:", codigo, descricao);
          // O AADSTS diz qual das causas de invalid_client e' a real (segredo
          // expirado, segredo errado, app nao encontrado). So' o numero vai para
          // a tela — a descricao completa fica no log.
          const aadsts = descricao.match(/AADSTS\d+/)?.[0];
          return marcarSeVencido(
            token,
            expiresAt,
            aadsts ? `${codigo}/${aadsts}` : String(codigo),
          );
        }

        token.accessToken = data.id_token;
        token.refreshToken = data.refresh_token ?? token.refreshToken;
        token.expiresAt =
          expDoJwt(data.id_token) ??
          Math.floor(Date.now() / 1000) + (data.expires_in ?? 3600);
        delete token.error;
        delete token.errorCode;
      } catch (e) {
        // Rede/timeout: transitorio por definicao, nunca motivo pra derrubar
        // uma sessao cujo token ainda esta' dentro da validade.
        console.error("[AUTH] Erro de rede ao renovar token:", e);
        return marcarSeVencido(token, expiresAt, "erro_de_rede");
      }

      return token;
    },
    async session({ session, token }) {
      // Token marcado como morto (passou do proprio exp e nao renovou) nao vai
      // para o cliente. Manter o token quando a renovacao falha e' proposital
      // enquanto ele ainda vale — mas depois de vencido ele so' gera erro cru na
      // tela ("Key ... not found in JWKS" quando o Azure ja' rotacionou a chave
      // que o assinou), em vez do aviso de sessao expirada que o usuario entende.
      session.accessToken = token.error
        ? undefined
        : (token.accessToken as string | undefined);
      session.expiresAt = token.expiresAt as number | undefined;
      session.error = token.error as "RefreshAccessTokenError" | undefined;
      session.errorCode = token.errorCode as string | undefined;
      if (token.sub) {
        session.user.id = token.sub;
      }
      return session;
    },
    async redirect({ url, baseUrl }) {
      // Sempre o pathname interno + host desta request. AUTH_URL na Vercel
      // (producao vs preview) nao pode mandar /consumidor de volta para /.
      const path = callbackUrlSeguro(url);
      return `${baseUrl}${path}`;
    },
  },
  pages: {
    signIn: "/login",
  },
  debug: process.env.NODE_ENV === "development",
  trustHost: true,
  secret: process.env.AUTH_SECRET,
  logger: {
    error(error) {
      console.error("[AUTH ERROR]", error);
      if (error.cause) console.error("[AUTH CAUSE]", error.cause);
    },
  },
});
