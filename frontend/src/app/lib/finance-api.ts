import { getAuthHeaders } from "./api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";

export interface TaxCode {
  id: number;
  codigo: string;
  descricao: string;
  aliquota_total: number;
  aliquota_iss: number;
  aliquota_pis: number;
  aliquota_cofins: number;
  aliquota_irrf: number;
  aliquota_csll: number;
  ativo: boolean;
  criado_em: string;
  criado_por: string;
}

export interface TaxCodeCreate {
  codigo: string;
  descricao: string;
  aliquota_total: number;
  aliquota_iss: number;
  aliquota_pis: number;
  aliquota_cofins: number;
  aliquota_irrf: number;
  aliquota_csll: number;
}

export type TipoCobranca = "mensal" | "hora" | "avulso" | "exito" | "prolabore" | "partido";
export type NaturezaPagamento = "captacao" | "performance" | "captacao_performance" | "projeto_opt";
export type TipoDocumento = "nf" | "emitir" | "recebimento_manual" | "recibo";

export const TIPOS_COBRANCA: TipoCobranca[] = ["mensal", "hora", "avulso", "exito", "prolabore", "partido"];
export const NATUREZAS_PAGAMENTO: NaturezaPagamento[] = ["captacao", "performance", "captacao_performance", "projeto_opt"];
export const TIPOS_DOCUMENTO: TipoDocumento[] = ["nf", "emitir", "recebimento_manual", "recibo"];

export const LABEL_TIPO_COBRANCA: Record<TipoCobranca, string> = {
  mensal: "Mensal",
  hora: "Hora trabalhada",
  avulso: "Avulso",
  exito: "Êxito",
  prolabore: "Pró-labore",
  partido: "Partido",
};

export const LABEL_NATUREZA: Record<NaturezaPagamento, string> = {
  captacao: "Captação",
  performance: "Performance",
  captacao_performance: "Captação + Performance",
  projeto_opt: "Projeto OpT",
};

export const LABEL_TIPO_DOC: Record<TipoDocumento, string> = {
  nf: "NF emitida",
  emitir: "A emitir",
  recebimento_manual: "Recebimento manual",
  recibo: "Recibo",
};

async function _fetch<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...getAuthHeaders(), "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const taxCodeApi = {
  listar: (incluirInativos = false) =>
    _fetch<TaxCode[]>(`/api/tax-codes?incluir_inativos=${incluirInativos}`),
  getDefault: () => _fetch<TaxCode>("/api/tax-codes/default"),
  criar: (body: TaxCodeCreate) =>
    _fetch<TaxCode>("/api/tax-codes", { method: "POST", body: JSON.stringify(body) }),
  atualizar: (id: number, body: Partial<TaxCodeCreate>) =>
    _fetch<TaxCode>(`/api/tax-codes/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  desativar: (id: number) =>
    _fetch<TaxCode>(`/api/tax-codes/${id}/desativar`, { method: "POST" }),
};
