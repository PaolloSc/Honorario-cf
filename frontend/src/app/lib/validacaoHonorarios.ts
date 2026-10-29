import type { EscopoItem } from "@/types/contract";

// Regras da etapa 3 que dependem do conteúdo de cada honorário. Fica fora do
// ContractWizard para poder ser verificada sem React (validacaoHonorarios.check.ts).
const ROTULOS = {
  hora_trabalhada: "hora trabalhada",
  pro_labore: "pró-labore",
  mensalidade: "mensalidade",
  exito: "êxito",
  permuta: "permuta",
} as const;

type Honorario = keyof typeof ROTULOS;

export function errosDoEscopo(
  escopo: Pick<EscopoItem, "honorarios" | Honorario>,
  label: string,
): string[] {
  const errors: string[] = [];
  const pl = escopo.pro_labore;
  if (
    escopo.honorarios.includes("pro_labore") &&
    pl?.tipo_parcelamento === "customizado" &&
    !pl.parcelamento_customizado?.trim()
  ) {
    // Sem o texto, o contrato cairia em "parcela única": descreva o parcelamento.
    errors.push(`${label}: descreva o parcelamento customizado do pró-labore.`);
  }
  // Mesmas regras do backend (422): êxito de 0 a 100 e valor maior que zero.
  const pct = escopo.exito?.percentual;
  if (escopo.honorarios.includes("exito") && pct != null && (pct < 0 || pct > 100)) {
    errors.push(`${label}: o percentual de êxito deve ficar entre 0 e 100.`);
  }
  const ex = escopo.exito;
  if (
    escopo.honorarios.includes("exito") &&
    ex?.subtipo === "percentual_variavel" &&
    !ex.faixas_percentual?.some((f) => f.faixa.trim() && f.percentual.trim())
  ) {
    errors.push(`${label}: êxito de percentual variável precisa de ao menos uma faixa com valor e percentual.`);
  }
  const valores: [Honorario, number | null | undefined, string][] = [
    ["hora_trabalhada", escopo.hora_trabalhada?.valor_hora, "hora trabalhada"],
    ["mensalidade", escopo.mensalidade?.faixas_preco?.length ? undefined : escopo.mensalidade?.valor, "mensalidade"],
    [
      "pro_labore",
      pl?.tipo_parcelamento === "customizado" && pl.parcelamento_customizado?.trim() ? undefined : pl?.valor_total,
      "pró-labore",
    ],
  ];
  for (const [hon, valor, rotulo] of valores) {
    if (escopo.honorarios.includes(hon) && valor != null && valor <= 0) {
      errors.push(`${label}: informe o valor de ${rotulo} (maior que zero).`);
    }
  }
  if (escopo.honorarios.includes("pro_labore") && pl?.tipo_parcelamento === "mensal") {
    const n = pl.numero_parcelas ?? 0;
    const v = pl.valor_parcela ?? 0;
    if (n <= 0 || v <= 0) {
      errors.push(`${label}: pró-labore mensal precisa do número de parcelas e do valor da parcela.`);
    } else if ((pl.valor_total ?? 0) > 0 && Math.abs(n * v - pl.valor_total) > 0.01 * n) {
      errors.push(`${label}: pró-labore: número de parcelas × valor da parcela não bate com o valor total.`);
    }
  }
  if (escopo.honorarios.includes("permuta") && !escopo.permuta?.objeto_permuta?.trim()) {
    errors.push(`${label}: informe o objeto da permuta.`);
  }
  if (escopo.honorarios.includes("exito") && escopo.exito?.forma_pagamento?.trim().toLowerCase() === "a definir") {
    errors.push(`${label}: descreva a forma de pagamento do êxito (\"Outro\" sem texto).`);
  }
  for (const hon of Object.keys(ROTULOS) as Honorario[]) {
    const h = escopo[hon];
    if (
      escopo.honorarios.includes(hon) &&
      h?.tem_desconto &&
      (h.desconto_tipo ?? "percentual") === "percentual" &&
      (h.desconto_percentual ?? 0) > 100
    ) {
      errors.push(`${label}: o desconto de ${ROTULOS[hon]} não pode passar de 100%.`);
    }
  }
  return errors;
}
