import { fetchAutenticado } from "./api";
import type { StatusFatura } from "./emissao";

const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";

export interface EmissorOut {
  configurado: boolean;
  cnpj: string | null;
  razao_social: string | null;
  inscricao_municipal: string | null;
  municipio_ibge: string | null;
  op_simp_nac: string | null;
  reg_ap_trib_sn: string | null;
  reg_esp_trib: string | null;
  serie_dps: string | null;
  ambiente: string | null;
  ativo: boolean;
  tem_certificado: boolean;
  cert_titular: string | null;
  cert_validade: string | null;
  producao_permitida: boolean;
}

export interface EmissorIn {
  cnpj: string;
  razao_social: string;
  inscricao_municipal: string | null;
  municipio_ibge: string;
  op_simp_nac: string;
  reg_ap_trib_sn: string | null;
  reg_esp_trib: string;
  serie_dps: string;
  ambiente: "homologacao";
  ativo: boolean;
}

export interface Servico {
  id: number;
  nome: string;
  descricao_padrao: string;
  codigo_lc116: string | null;
  c_trib_nac: string;
  c_trib_mun: string | null;
  nbs: string | null;
  aliquota_iss: string | null;
  iss_retido_padrao: boolean;
  incluir_ibscbs: boolean;
  c_ind_op: string | null;
  cst_ibscbs: string | null;
  c_class_trib: string | null;
  ativo: boolean;
}
export type ServicoIn = Omit<Servico, "id">;

export interface Tomador {
  id: number;
  documento: string;
  nome: string;
  emails: string[];
  inscricao_municipal: string | null;
  optante_simples: boolean;
  orgao_publico: boolean;
  cep: string | null;
  logradouro: string | null;
  numero: string | null;
  complemento: string | null;
  bairro: string | null;
  municipio_ibge: string | null;
  uf: string | null;
  origem: string;
  ativo: boolean;
}
export type TomadorIn = Omit<Tomador, "id" | "origem" | "ativo">;

export interface Faturamento {
  contract_id: string;
  origem: "legalone" | "honorario";
  tomador_id: number | null;
  servico_id: number | null;
  gera_rascunho_mensal: boolean;
}

export interface Fatura {
  id: number;
  contract_id: string;
  tomador_id: number;
  servico_id: number;
  competencia: string;
  descricao: string;
  valor_bruto: string;
  vencimento: string | null;
  parcela_num: number;
  parcela_total: number;
  origem: string;
  status: StatusFatura;
  criada_por: string;
  aprovada_por: string | null;
}

export interface FaturasResposta {
  itens: Fatura[];
  totais: Record<string, { quantidade: number; valor: string }>;
}

export interface NovaFatura {
  contract_id: string;
  tomador_id: number;
  servico_id: number;
  competencia: string;
  descricao?: string;
  valor_bruto: string;
  vencimento?: string | null;
}

export interface NotaEmitida {
  id: number;
  fatura_id: number;
  status: "processando" | "autorizada" | "rejeitada" | "cancelada";
  ambiente: string;
  dps_serie: string;
  dps_numero: number;
  chave_acesso: string | null;
  numero_nfse: string | null;
  valor_servicos: string;
  iss: string;
  erro_codigo: string | null;
  erro_mensagem: string | null;
  emitida_em: string | null;
  emitida_por: string;
  criado_em: string | null;
  tem_xml: boolean;
}

export interface EventoNota {
  id: number;
  tipo: string;
  payload: Record<string, unknown>;
  criado_em: string | null;
}

async function pedir<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetchAutenticado(`${API_BASE}${path}`, init);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.status === 204 ? (undefined as T) : r.json();
}

const JSON_HEADERS = { "Content-Type": "application/json" };
const enviar = (method: string, body: unknown): RequestInit => ({
  method,
  headers: JSON_HEADERS,
  body: JSON.stringify(body),
});

export const emissaoApi = {
  emissor: () => pedir<EmissorOut>("/api/emissor"),
  salvarEmissor: (b: EmissorIn) => pedir<EmissorOut>("/api/emissor", enviar("PUT", b)),
  enviarCertificado: (pfx: File, senha: string) => {
    // multipart: o navegador define o Content-Type com o boundary
    const f = new FormData();
    f.append("pfx", pfx);
    f.append("senha", senha);
    return pedir<EmissorOut>("/api/emissor/certificado", { method: "POST", body: f });
  },

  servicos: (todos = true) => pedir<Servico[]>(`/api/servicos?todos=${todos}`),
  criarServico: (b: ServicoIn) => pedir<Servico>("/api/servicos", enviar("POST", b)),
  alterarServico: (id: number, b: Partial<ServicoIn>) => pedir<Servico>(`/api/servicos/${id}`, enviar("PATCH", b)),

  tomadores: (q = "") => pedir<Tomador[]>(`/api/tomadores?q=${encodeURIComponent(q)}`),
  criarTomador: (b: TomadorIn) => pedir<Tomador>("/api/tomadores", enviar("POST", b)),
  alterarTomador: (id: number, b: Partial<TomadorIn> & { ativo?: boolean }) =>
    pedir<Tomador>(`/api/tomadores/${id}`, enviar("PATCH", b)),
  tomadorDeContrato: (contractId: string) =>
    pedir<Tomador>(`/api/tomadores/de-contrato/${encodeURIComponent(contractId)}`, { method: "POST" }),

  faturamento: (contractId: string) => pedir<Faturamento>(`/api/contratos/${encodeURIComponent(contractId)}/faturamento`),
  definirFaturamento: (contractId: string, b: Omit<Faturamento, "contract_id">) =>
    pedir<Faturamento>(`/api/contratos/${encodeURIComponent(contractId)}/faturamento`, enviar("PUT", b)),

  faturas: (status?: string) =>
    pedir<FaturasResposta>(`/api/faturas${status ? `?status=${status}` : ""}`),
  criarFatura: (b: NovaFatura) => pedir<Fatura>("/api/faturas", enviar("POST", b)),
  aprovarFatura: (id: number) => pedir<Fatura>(`/api/faturas/${id}/aprovar`, { method: "POST" }),
  excluirFatura: (id: number) => pedir<void>(`/api/faturas/${id}`, { method: "DELETE" }),
  /** A chave identifica a INTENÇÃO de emitir: repetir a mesma chave devolve a mesma nota. */
  emitir: (id: number, chave: string) =>
    pedir<NotaEmitida>(`/api/faturas/${id}/emitir`, { method: "POST", headers: { "Idempotency-Key": chave } }),

  notas: () => pedir<NotaEmitida[]>("/api/nfse-emitidas"),
  nota: (id: number) => pedir<NotaEmitida & { eventos: EventoNota[] }>(`/api/nfse-emitidas/${id}`),
  consultarNota: (id: number) => pedir<NotaEmitida>(`/api/nfse-emitidas/${id}/consultar`, { method: "POST" }),
  baixarXml: async (n: NotaEmitida) => {
    const r = await fetchAutenticado(`${API_BASE}/api/nfse-emitidas/${n.id}/xml`);
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `NFSe-${n.chave_acesso ?? n.id}.xml`;
    a.click();
    URL.revokeObjectURL(url);
  },
};
