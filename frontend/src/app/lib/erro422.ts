// Mensagem legível para o 422 do FastAPI (detail como lista de {msg}). As regras do
// contrato levantam ValueError ("Value error, Escopo 1: ..."): o prefixo é ruído.
export function mensagemDo422(corpo: string): string | null {
  try {
    const detail = JSON.parse(corpo)?.detail;
    if (typeof detail === "string") return detail;
    if (!Array.isArray(detail)) return null;
    const msgs = detail
      .map((d) => (typeof d?.msg === "string" ? d.msg.replace(/^Value error,\s*/, "") : null))
      .filter((m): m is string => !!m);
    return msgs.length ? msgs.join(" ") : null;
  } catch {
    return null;
  }
}

/** Texto para mostrar ao usuário: o 422 do backend vira só a regra violada; o resto passa. */
export function textoDoErro(erro: unknown): string {
  const bruto = erro instanceof Error ? erro.message : "Erro desconhecido";
  const m = /^API error 422: ([\s\S]*)$/.exec(bruto);
  return (m && mensagemDo422(m[1])) || bruto;
}

export function ehErro422(erro: unknown): boolean {
  return erro instanceof Error && /^API error 422: /.test(erro.message) && textoDoErro(erro) !== erro.message;
}

const HONORARIOS = ["honorarios", "hora_trabalhada", "pro_labore", "mensalidade", "exito", "permuta"];

/** Etapa do wizard onde fica o campo do caminho do 422 (ex.: "escopos.0.pro_labore.numero_parcelas" -> 3).
 *  O que não é das etapas 1 a 5 (e-mail, envio, ajustes de texto) está na própria etapa 7. */
export function etapaDoCampo(caminho: string): number {
  const [raiz, , sub] = caminho.split(".");
  if (raiz === "contratantes" || raiz === "incluir_partes_relacionadas") return 1;
  if (raiz === "escopos") return sub && HONORARIOS.includes(sub) ? 3 : 2;
  if (raiz === "acessorios") return 4;
  if (raiz === "participacao") return 5;
  return 7;
}

/** 422 por campo: { "escopos.0.pro_labore.numero_parcelas": "Escopo 1: ..." }. O caminho é o
 *  loc do backend sem "body" (e sem "form_data", na edição de contrato salvo). Erro sem campo
 *  (loc só com "body") fica de fora: a tela mostra esse pelo textoDoErro. */
export function errosPorCampo(erro: unknown): Record<string, string> {
  const m = erro instanceof Error ? /^API error 422: ([\s\S]*)$/.exec(erro.message) : null;
  const campos: Record<string, string> = {};
  if (!m) return campos;
  try {
    const detail = JSON.parse(m[1])?.detail;
    if (!Array.isArray(detail)) return campos;
    for (const d of detail) {
      if (!Array.isArray(d?.loc) || typeof d?.msg !== "string") continue;
      const loc = d.loc.slice(d.loc[0] === "body" ? 1 : 0);
      if (loc[0] === "form_data") loc.shift();
      if (!loc.length) continue;
      const chave = loc.join(".");
      campos[chave] ??= d.msg.replace(/^Value error,\s*/, "");
    }
  } catch {
    // corpo não JSON: nenhum campo
  }
  return campos;
}
