function resolveApiBase(): string {
  // 1. Vercel environment variable takes priority
  const envBase = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  if (envBase) return envBase;

  // 2. In browser (production), use same domain — Railway typically runs on same domain via proxy
  if (typeof window !== "undefined") {
    const protocol = window.location.protocol;
    const host = window.location.hostname;
    // Vercel serverless functions are at /api on the same domain
    return `${protocol}//${host}`;
  }

  // 3. Development fallback
  return "http://127.0.0.1:8000";
}

const API_BASE = resolveApiBase();

let _accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  _accessToken = token;
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  let res: Response;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8000);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options?.headers as Record<string, string>) || {}),
  };
  if (_accessToken) {
    headers["Authorization"] = `Bearer ${_accessToken}`;
  }

  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: options?.signal || controller.signal,
      headers,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`Tempo esgotado ao conectar na API (${API_BASE}).`);
    }
    const detail = err instanceof Error ? err.message : "erro desconhecido";
    throw new Error(`Falha ao conectar na API (${API_BASE}): ${detail}`);
  } finally {
    clearTimeout(timeoutId);
  }

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }

  return res.json();
}

export async function generateContract(data: unknown) {
  return request<{
    success: boolean;
    message: string;
    contract_id?: string;
    download_url?: string;
  }>("/api/contract/generate", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function downloadContract(contractId: string) {
  const headers: Record<string, string> = {};
  if (_accessToken) {
    headers["Authorization"] = `Bearer ${_accessToken}`;
  }
  const res = await fetch(
    `${API_BASE}/api/contract/${contractId}/download`,
    { headers }
  );
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Erro ao baixar contrato: ${res.status} - ${body}`);
  }
  return res.blob();
}

export async function sendEmail(data: {
  contract_id: string;
  destinatario_email: string;
  destinatario_nome: string;
  assunto?: string;
}) {
  return request<{ success: boolean; message: string }>("/api/email/send", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function sendParticipacao(data: {
  contract_id: string;
  cliente_nome: string;
  percentual_ou_valor?: string;
  para_quem?: string;
  natureza?: string;
  responsavel_captacao?: string;
  responsavel_gestao?: string;
  contato_financeiro_cliente?: string;
}) {
  return request<{ success: boolean; message: string }>("/api/email/send-participacao", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function sendForSignature(data: {
  contract_id: string;
  signatarios: Array<{ email: string; name: string; role: string }>;
}) {
  return request<{ success: boolean; message: string }>(
    "/api/docuseal/send-for-signature",
    {
      method: "POST",
      body: JSON.stringify(data),
    }
  );
}

export async function lookupCNPJ(cnpj: string) {
  const cnpjClean = cnpj.replace(/\D/g, "");
  return request<{
    cnpj: string;
    razao_social: string;
    nome_fantasia: string;
    endereco: string;
    situacao_cadastral: string;
  }>(`/api/cnpj/${cnpjClean}`);
}

// ── Contracts Management ─────────────────────────────────────────

export interface ContractSummary {
  contract_id: string;
  status: string;
  client_name: string;
  client_email: string;
  current_version: number;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface ContractListResponse {
  contracts: ContractSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface VersionSummary {
  version_number: number;
  file_path: string | null;
  docuseal_submission_id: string | null;
  created_by?: string;
  created_at: string;
}

export interface AuditEntry {
  action: string;
  detail: string | null;
  version_number: number | null;
  user_email?: string;
  created_at: string;
}

export interface ContractDetail {
  contract_id: string;
  status: string;
  client_name: string;
  client_email: string;
  current_version: number;
  created_by?: string;
  updated_by?: string;
  created_at: string;
  updated_at: string;
  versions: VersionSummary[];
  audit_log: AuditEntry[];
}

export interface ContractFormDataResponse {
  contract_id: string;
  version_number: number;
  form_data: Record<string, unknown>;
}

export async function listContracts(params?: {
  page?: number;
  page_size?: number;
  status?: string;
  search?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.page_size) qs.set("page_size", String(params.page_size));
  if (params?.status) qs.set("status", params.status);
  if (params?.search) qs.set("search", params.search);
  const query = qs.toString();
  return request<ContractListResponse>(`/api/contracts${query ? `?${query}` : ""}`);
}

export async function getContract(contractId: string) {
  return request<ContractDetail>(`/api/contracts/${contractId}`);
}

export async function getContractFormData(contractId: string, version?: number) {
  const qs = version ? `?version=${version}` : "";
  return request<ContractFormDataResponse>(`/api/contracts/${contractId}/form-data${qs}`);
}

export async function updateContract(contractId: string, formData: Record<string, unknown>) {
  return request<{
    success: boolean;
    message: string;
    contract_id: string;
    version: number;
    download_url: string;
  }>(`/api/contracts/${contractId}`, {
    method: "PUT",
    body: JSON.stringify({ form_data: formData }),
  });
}

export async function updateContractStatus(contractId: string, status: string) {
  return request<{ success: boolean; status: string }>(
    `/api/contracts/${contractId}/status?status=${encodeURIComponent(status)}`,
    { method: "PATCH" }
  );
}
