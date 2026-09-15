import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Apaga os cookies de autenticacao e devolve a pessoa para o login.
 *
 * Por que precisa existir: os cookies do next-auth sao HttpOnly, entao o
 * JavaScript da pagina nao alcanca eles. Quem consegue expirar e' o servidor,
 * e a unica rota que fazia isso era o signOut — que passa pelo mesmo POST
 * protegido por CSRF que quebra quando o cookie de CSRF esta' corrompido. O
 * caminho de limpeza dependia da peca quebrada, e sobrava mandar o usuario
 * limpar dados do site na mao.
 *
 * E' GET de proposito, para ser um link clicavel por quem ja' esta' travado.
 * O unico efeito possivel de um acionamento indevido e' deslogar — nenhum dado
 * e' lido nem alterado.
 */

// Cobre os dois prefixos que o @auth/core usa conforme o ambiente, os nomes
// legados do next-auth v4 e o cookie do login de desenvolvimento.
const BASES = [
  "authjs.session-token",
  "authjs.csrf-token",
  "authjs.callback-url",
  "authjs.pkce.code_verifier",
  "authjs.state",
  "authjs.nonce",
  "next-auth.session-token",
  "next-auth.csrf-token",
  "next-auth.callback-url",
  "next-auth.pkce.code_verifier",
  "dev_session",
];

const PREFIXOS = ["", "__Secure-", "__Host-"];

function nomesParaLimpar(): string[] {
  const nomes: string[] = [];
  for (const base of BASES) {
    for (const prefixo of PREFIXOS) {
      nomes.push(`${prefixo}${base}`);
      // Sessao grande e' fatiada pelo @auth/core em .0, .1, ... — sem apagar os
      // pedacos, o cookie volta a se remontar e a limpeza nao adianta nada.
      for (let i = 0; i < 6; i++) nomes.push(`${prefixo}${base}.${i}`);
    }
  }
  return nomes;
}

export async function GET(req: NextRequest) {
  const destino = new URL("/login?limpo=1", req.nextUrl.origin);
  const res = NextResponse.redirect(destino);
  const https = destino.protocol === "https:";

  for (const nome of nomesParaLimpar()) {
    // Cookie com prefixo __Secure-/__Host- so' e' aceito pelo navegador com
    // Secure; sem isso o Set-Cookie que apaga e' descartado em silencio.
    const precisaSecure = nome.startsWith("__");
    if (precisaSecure && !https) continue;
    res.cookies.set(nome, "", {
      path: "/",
      expires: new Date(0),
      maxAge: 0,
      secure: precisaSecure || https,
      httpOnly: true,
      sameSite: "lax",
    });
  }

  // Resposta nao pode ficar em cache, senao a limpeza "acontece" sem chegar ao
  // navegador na proxima vez.
  res.headers.set("Cache-Control", "no-store, max-age=0");
  return res;
}
