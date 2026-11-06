// Revisão por IA e Prévia só valem para os Dados do contrato com que foram feitas. Estas funções
// dizem se ainda valem; sem React e sem rede (ver GLOSSARY.md: Revisão desatualizada).

// O Envio (e-mails, testemunhas, sócio) e a versão do formato não mudam o texto do contrato.
type Dados = { envio?: unknown; versao_formato?: unknown };

export function chaveDaRevisao(data: Dados): string {
  const { envio: _envio, versao_formato: _versao, ...texto } = data;
  return JSON.stringify(texto);
}

/** nenhuma: nunca revisou nesta sessão; em_dia: reaproveita; desatualizada: refazer e avisar. */
export function situacaoDaRevisao(ultima: { chave: string } | null, data: Dados): "nenhuma" | "em_dia" | "desatualizada" {
  if (!ultima) return "nenhuma";
  return ultima.chave === chaveDaRevisao(data) ? "em_dia" : "desatualizada";
}
