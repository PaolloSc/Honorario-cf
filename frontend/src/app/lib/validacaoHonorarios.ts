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
