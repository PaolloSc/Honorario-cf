import type { EscopoItem } from "@/types/contract";

// Regras da etapa 3 que dependem do conteúdo de cada honorário. Fica fora do
// ContractWizard para poder ser verificada sem React (validacaoHonorarios.check.ts).
export function errosDoEscopo(escopo: Pick<EscopoItem, "honorarios" | "pro_labore">, label: string): string[] {
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
  return errors;
}
