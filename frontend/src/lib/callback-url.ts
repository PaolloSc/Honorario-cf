/** Destino pos-login: so caminhos internos. Absolutos (Auth.js manda a URL cheia;
 * na Vercel a origem do AUTH_URL pode diferir do preview) viram pathname. */
export function callbackUrlSeguro(raw: string | null | undefined): string {
  if (!raw) return "/";
  let valor = raw.trim();
  try {
    valor = decodeURIComponent(valor);
  } catch {
    /* ja veio decodificado */
  }
  if (!(valor.startsWith("/") && !valor.startsWith("//") && !valor.startsWith("/\\"))) {
    try {
      const u = new URL(valor);
      valor = `${u.pathname}${u.search}${u.hash}` || "/";
    } catch {
      return "/";
    }
  }
  if (!valor.startsWith("/") || valor.startsWith("//") || valor.startsWith("/\\")) {
    return "/";
  }
  // Voltar para o login (ou para o callback do Auth.js) geraria loop.
  if (valor.startsWith("/login") || valor.startsWith("/api/auth")) return "/";
  return valor;
}
