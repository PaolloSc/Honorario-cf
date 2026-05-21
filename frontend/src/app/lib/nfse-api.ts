import { getAuthHeaders } from "./api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";

export type NFSeStatus =
  | "auto" | "manual" | "pendente" | "sem_match" | "erro" | "cancelada";

export interface NFSeOut {
  id: number;
  cnpj_prestador: string;
  numero: string;
  serie: string | null;
  competencia: string;
  data_emissao: string;
  tomador_doc: string;
  tomador_nome: string | null;
  valor_servicos: string;
  valor_liquido: string;
  cancelada: boolean;
  status_matching: NFSeStatus;
  contract_id: string | null;
  participacao_id: number | null;
  pagamento_id: number | null;
  motivo: string | null;
}

export interface HealthResponse {
  enabled: boolean;
  last_job?: {
    iniciado_em: string | null;
    finalizado_em: string | null;
    status: string;
    total_nfs: number;
    erros: number;
  } | null;
  now?: string;
}

async function _fetch<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...getAuthHeaders(), "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const nfseApi = {
  health: () => _fetch<HealthResponse>("/api/nfse/health"),

  listar: (params: { cnpj_prestador?: string; competencia_mes?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params.cnpj_prestador) q.set("cnpj_prestador", params.cnpj_prestador);
    if (params.competencia_mes) q.set("competencia_mes", params.competencia_mes);
    if (params.status) q.set("status", params.status);
    return _fetch<NFSeOut[]>(`/api/nfse?${q.toString()}`);
  },

  vincular: (nfse_id: number, body: { contract_id: string; motivo?: string }) =>
    _fetch<NFSeOut>(`/api/nfse/${nfse_id}/vincular`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  syncManual: (cnpj_prestador: string) =>
    _fetch<{ ok: boolean; msg: string }>(`/api/nfse/sync?cnpj_prestador=${cnpj_prestador}`, {
      method: "POST",
    }),
};

export interface CredencialPbhOut {
  id: number;
  cnpj_prestador: string;
  ativo: boolean;
  criado_em: string;
  criado_por: string;
  motivo_inativacao: string | null;
}

export const credencialApi = {
  listar: () => _fetch<CredencialPbhOut[]>("/api/admin/credencial-pbh"),
  upsert: (body: { cnpj_prestador: string; login: string; senha: string }) =>
    _fetch<CredencialPbhOut>("/api/admin/credencial-pbh", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  desativar: (cnpj: string, motivo?: string) => {
    const q = new URLSearchParams();
    if (motivo) q.set("motivo", motivo);
    return _fetch<CredencialPbhOut>(
      `/api/admin/credencial-pbh/${cnpj}/desativar?${q.toString()}`,
      { method: "POST" }
    );
  },
};
