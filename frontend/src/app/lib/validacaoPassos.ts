import type { ContratoFormData } from "@/types/contract";

// Validação das etapas 2 a 5 do wizard (cada mensagem nomeia o campo que falta).
// Fica fora do ContractWizard para rodar sem React (validacaoPassos.check.ts).
// Os asteriscos (*) das telas seguem estas regras.
const text = (v: unknown) => (typeof v === "string" ? v.trim() : "");

export function validateEscopos(data: ContratoFormData): string[] {
  const errors: string[] = [];

  if (data.escopos.length === 0) {
    errors.push("Selecione pelo menos um escopo.");
    return errors;
  }

  data.escopos.forEach((escopo, index) => {
    const label = `Escopo ${index + 1}`;

    if (escopo.tipo === "consultoria_elaboracao_documentos" && !text(escopo.documentos)) {
      errors.push(`${label}: informe os documentos a elaborar.`);
    }

    if (escopo.tipo === "consultoria_opiniao_legal" && !text(escopo.consulta)) {
      errors.push(`${label}: informe a consulta ou tema do parecer.`);
    }

    if (escopo.tipo === "outro" && !text(escopo.descricao_custom)) {
      errors.push(`${label}: descreva o escopo.`);
    }
  });

  return errors;
}

export function validateAcessorios(_data: ContratoFormData): string[] {
  return [];
}

// Mesmo critério da ficha (backend/app/utils/participacao.py): sem valor_tipo,
// o wizard mostra "percentual" marcado.
function temValor(tipo: string | undefined, pct?: string, valor?: number, outro?: string): boolean {
  const t = tipo || "percentual";
  if (t === "percentual") return Boolean(pct?.toString().trim());
  if (t === "valor") return valor != null;
  return Boolean(outro?.trim());
}

export function validateParticipacao(data: ContratoFormData): string[] {
  const errors: string[] = [];
  if (!data.participacao.responsavel_gestao?.trim()) {
    errors.push("Informe o responsável pela gestão do contrato.");
  }

  // Cada advogado marcado precisa de valor próprio ou de um valor geral — senão a
  // ficha chega ao financeiro sem valor nenhum.
  const p = data.participacao;
  if (p.tem_participacao) {
    const temGeral =
      (p.valor_tipo != null && temValor(p.valor_tipo, p.valor_percentual, p.valor_monetario, p.valor_outro)) ||
      Boolean(p.percentual_ou_valor?.trim());
    if (!temGeral) {
      for (const part of p.participantes ?? []) {
        if (!temValor(part.valor_tipo, part.percentual, part.valor_monetario, part.valor_outro)) {
          errors.push(`Informe o valor de ${part.nome} ou o critério geral da participação.`);
        }
      }
    }
  }
  return errors;
}

