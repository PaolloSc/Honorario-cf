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
