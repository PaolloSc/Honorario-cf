// Entrada por link de convite. Em navegador novo, o SessionProvider (/api/auth/session)
// e o signIn (/api/auth/csrf) correm juntos e cada um pode gerar o cookie de CSRF do
// Auth.js: o último a chegar vence e o token que o signIn usou deixa de casar
// ("MissingCSRF", 6 de 10 visitas medidas). A segunda tentativa já parte do cookie
// gravado e passa; o token do convite não é consumido pela primeira.
export type ResultadoEntrada = { ok?: boolean; error?: string | null } | undefined;

export async function entrarComConvite(
  entrar: () => Promise<ResultadoEntrada>,
  tentativas = 3,
): Promise<boolean> {
  for (let i = 0; i < tentativas; i++) {
    try {
      const r = await entrar();
      if (r?.ok && !r.error) return true;
    } catch {
      /* falha de rede: tenta de novo */
    }
  }
  return false;
}
