import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Pin the workspace root to this app, silencing the multiple-lockfiles
  // inference warning caused by a stray package-lock.json in a parent dir.
  outputFileTracingRoot: path.join(__dirname),
  // A calculadora de honorários é um HTML autocontido em public/calculadora/,
  // e carrega docx.umd.js e jspdf.umd.min.js por caminho RELATIVO.
  // Precisa ser redirect, não rewrite: um rewrite serve o HTML mantendo a URL
  // em /calculadora (sem barra), e aí o relativo resolve para /docx.umd.js na
  // raiz — 404, as libs não carregam e nenhum documento é gerado, em silêncio.
  // Com redirect a URL vira o caminho real e os relativos resolvem ao lado dela.
  //
  // /jesp e' como o escritorio chama o contrato de acao de consumo.
  async redirects() {
    return [
      { source: "/calculadora", destination: "/calculadora/index.html", permanent: false },
      { source: "/jesp", destination: "/consumidor", permanent: false },
    ];
  },
};

export default nextConfig;
