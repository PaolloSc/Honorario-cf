// Mesma regra do backend (utils/parcelas.py): em centavos, a última parcela absorve a diferença.
export function dividirParcelas(total: number, n: number): number[] {
  if (!(n >= 1) || !(total > 0)) return [];
  const centavos = Math.round(total * 100);
  const base = Math.floor(centavos / n);
  const parcelas = Array<number>(n).fill(base);
  parcelas[n - 1] += centavos - base * n;
  return parcelas.map((c) => c / 100);
}

/** Dia (1-31) de uma data ISO "aaaa-mm-dd", ou undefined. */
export function diaDaData(iso?: string): number | undefined {
  const d = Number((iso ?? "").slice(8, 10));
  return d >= 1 && d <= 31 ? d : undefined;
}
