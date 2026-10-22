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
