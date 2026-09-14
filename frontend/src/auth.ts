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
    const json = Buffer.from(
      payload.replace(/-/g, "+").replace(/_/g, "/"),
      "base64",
    ).toString("utf8");
    const exp = JSON.parse(json)?.exp;
    return typeof exp === "number" ? exp : undefined;
  } catch {
    return undefined;
  }
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
        return token;
      }

      // Margem de 5min: o refetch da sessao no cliente roda a cada 5min, entao o
      // token precisa ser renovado antes de a janela seguinte comecar. Com os 60s
      // de antes havia ate ~4min de buraco em que o front mandava token vencido.
      const expiresAt = typeof token.expiresAt === "number" ? token.expiresAt : undefined;
      if (token.accessToken && expiresAt && Date.now() < expiresAt * 1000 - 300_000) {
        return token;
      }

      if (!token.refreshToken) {
        // Sem refresh token nao ha como renovar: marca a sessao para novo login
        // em vez de devolver um accessToken vencido que so' gera 401.
        delete token.accessToken;
        token.error = "RefreshAccessTokenError";
        return token;
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
        const data = await res.json();

        if (!res.ok || !data.id_token) {
          // AADSTS700082 (refresh token vencido por inatividade), consentimento
          // revogado, senha trocada... Sem sinalizar, a sessao seguia "valida"
          // com id_token morto e a API devolvia 401 ate' limpar cookie na mao.
          throw new Error(
            `${res.status} ${data?.error ?? "sem id_token"}: ${data?.error_description ?? ""}`,
          );
        }

        token.accessToken = data.id_token;
        token.refreshToken = data.refresh_token ?? token.refreshToken;
        token.expiresAt =
          expDoJwt(data.id_token) ??
          Math.floor(Date.now() / 1000) + (data.expires_in ?? 3600);
        delete token.error;
      } catch (e) {
        console.error("[AUTH] Token refresh failed:", e);
        delete token.accessToken;
        token.error = "RefreshAccessTokenError";
      }

      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string | undefined;
      session.expiresAt = token.expiresAt as number | undefined;
      session.error = token.error as "RefreshAccessTokenError" | undefined;
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
