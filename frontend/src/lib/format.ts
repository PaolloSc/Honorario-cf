// 10 -> "10%", 10.5 / "10.5" / "10,5" -> "10,5%". Texto nao numerico volta como veio.
export function formatPercentual(v: number | string): string {
  const n = typeof v === "number" ? v : Number(String(v).trim().replace(",", "."));
  if (!Number.isFinite(n)) return String(v).endsWith("%") ? String(v) : `${v}%`;
  return `${n.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`;
}
