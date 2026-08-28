function resolveApiBase(): string {
  // 1. Vercel environment variable takes priority
  const envBase = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  if (envBase) return envBase;

  // 2. In browser (production), use same domain — Railway typically runs on same domain via proxy
  if (typeof window !== "undefined") {
    const protocol = window.location.protocol;
    const host = window.location.hostname;
    // Dev local: backend separado em :8000
    if (host === "localhost" || host === "127.0.0.1") {
      return `${protocol}//${host}:8000`;
    }
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

export function getAuthHeaders(): Record<string, string> {
  const h: Record<string, string> = {};
  if (_accessToken) h["Authorization"] = `Bearer ${_accessToken}`;
  Object.assign(h, getDevHeaders());
  return h;
}

function getDevHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  if (process.env.NEXT_PUBLIC_DEV_MODE !== "true") return {};
  const email = localStorage.getItem("dev_user_email");
  const role = localStorage.getItem("dev_user_role");
  const name = localStorage.getItem("dev_user_name");
  if (!email) return {};
  const h: Record<string, string> = { "X-Dev-User-Email": email };
  if (role) h["X-Dev-User-Role"] = role;
  if (name) h["X-Dev-User-Name"] = name;
  return h;
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
  Object.assign(headers, getDevHeaders());

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

export async function previewContract(contractId: string) {
  const res = await fetch(`${API_BASE}/api/contract/${contractId}/preview`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Erro ao carregar visualização: ${res.status}`);
  }
  return res.text();
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
  objeto_contrato?: string;
  valor_tipo?: string;
  valor_percentual?: string;
  valor_monetario?: number;
  valor_outro?: string;
  participantes?: Array<{ nome: string; natureza: string; percentual?: string }>;
  responsavel_captacao?: string;
  responsavel_gestao?: string;
  contato_financeiro_nome?: string;
  contato_financeiro_email?: string;
  contato_financeiro_telefone?: string;
  base_tipo?: string;
  base_escopo_index?: number;
  base_honorario?: string;
  base_label?: string;
  categoria_cliente?: string;
  etiquetas?: string[];
  listas_transmissao?: string[];
}) {
  return request<{ success: boolean; message: string }>("/api/email/send-participacao", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listColaboradores(opts?: { participavel?: boolean }) {
  const qs = opts?.participavel ? "?participavel=true" : "";
  return request<{ colaboradores: Array<{ name: string; email: string; role: string }> }>(
    `/api/users/colaboradores${qs}`
  );
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

// ── Testemunhas (roster) ─────────────────────────────────────────

export interface Testemunha {
  id: number;
  nome: string;
  email: string;
  ativo: boolean;
  created_at: string;
}

export async function listTestemunhas(includeInactive = false) {
  const qs = includeInactive ? "?include_inactive=true" : "";
  return request<{ testemunhas: Testemunha[] }>(`/api/testemunhas${qs}`);
}

export async function createTestemunha(body: { nome: string; email: string }) {
  return request<Testemunha>("/api/testemunhas", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateTestemunha(
  id: number,
  body: { nome?: string; email?: string; ativo?: boolean }
) {
  return request<Testemunha>(`/api/testemunhas/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

// ── Colaboradores (roster) ───────────────────────────────────────

export interface Colaborador {
  id: number;
  nome: string;
  email: string | null;
  papel: string;
  ativo: boolean;
  ordem: number;
  participavel: boolean;
  created_at: string;
}

export const PAPEIS_COLABORADOR: Array<{ value: string; label: string }> = [
  { value: "socio", label: "Sócio(a)" },
  { value: "advogado", label: "Advogado(a)" },
  { value: "estagiario", label: "Estagiário(a)" },
  { value: "recepcionista", label: "Recepcionista" },
  { value: "financeiro", label: "Financeiro" },
  { value: "dev", label: "Desenvolvedor(a)" },
];

export async function listColaboradoresAdmin(includeInactive = true) {
  const qs = includeInactive ? "?include_inactive=true" : "?include_inactive=false";
  return request<{ colaboradores: Colaborador[] }>(`/api/colaboradores${qs}`);
}

export async function createColaborador(body: {
  nome: string;
  email?: string | null;
  papel: string;
  ordem?: number;
}) {
  return request<Colaborador>("/api/colaboradores", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateColaborador(
  id: number,
  body: { nome?: string; email?: string | null; papel?: string; ativo?: boolean; ordem?: number }
) {
  return request<Colaborador>(`/api/colaboradores/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteColaborador(id: number) {
  return request<{ success: boolean; id: number; ativo: boolean }>(
    `/api/colaboradores/${id}`,
    { method: "DELETE" }
  );
}

// ── Opções das tabelas do Legal One ──────────────────────────────

export interface LegalOneOpcao {
  id: number;
  tipo: LegalOneTipo;
  valor: string;
  ativo: boolean;
}

export type LegalOneTipo = "categoria_cliente" | "etiqueta" | "lista_transmissao";

export type LegalOneOpcoes = Record<LegalOneTipo, LegalOneOpcao[]>;

export const LEGALONE_TIPOS: Array<{ value: LegalOneTipo; label: string }> = [
  { value: "categoria_cliente", label: "Categoria do cliente" },
  { value: "etiqueta", label: "Etiqueta LO" },
  { value: "lista_transmissao", label: "Lista de transmissão" },
];

export async function listLegalOneOpcoes(incluirInativos = false) {
  const qs = incluirInativos ? "?incluir_inativos=true" : "";
  return request<LegalOneOpcoes>(`/api/legalone-opcoes${qs}`);
}

export async function createLegalOneOpcao(body: { tipo: LegalOneTipo; valor: string }) {
  return request<LegalOneOpcao>("/api/legalone-opcoes", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateLegalOneOpcao(id: number, ativo: boolean) {
  return request<LegalOneOpcao>(`/api/legalone-opcoes/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ ativo }),
  });
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

// ── Participações (Setor Financeiro) ─────────────────────────────

export interface Participacao {
  id: number;
  contract_id: string;
  beneficiario_email: string;
  beneficiario_nome: string;
  tipo_honorario: string;
  percentual_captacao: number;
  percentual_performance: number;
  percentual_total: number;
  motivo_captacao: string | null;
  motivo_performance: string | null;
  natureza: string;
  cliente_cpf_cnpj: string | null;
  data_inicio: string;
  vinculo_ativo: boolean;
  data_fim_vinculo: string | null;
  aprovado_por: string | null;
  observacoes: string | null;
  limite_temporal_anos: number | null;
  data_limite_temporal: string | null;
  total_pago: number;
  created_at: string;
}

export type PagamentoStatus = "a_receber" | "aguardando_pagamento" | "pago";

export interface Pagamento {
  id: number;
  participacao_id: number;
  data_recebimento: string;
  valor_bruto: number | null;
  imposto_total: number;
  valor_liquido_recebido: number;
  valor_participacao: number;
  dentro_limite_temporal: boolean;
  observacoes: string | null;
  status: PagamentoStatus;
  parcela_num: number;
  parcela_total: number;
  nf_referencia: string | null;
  tax_code_id: number | null;
  tax_code_codigo: string | null;
  aliquota_aplicada: number | null;
  tipo_cobranca: string | null;
  natureza_pagamento: string | null;
  tipo_documento: string;
  created_at: string;
}

export interface ResumoParticipacao {
  participacao: Participacao;
  pagamentos: Pagamento[];
  total_recebido_liquido: number;
  total_participacao: number;
}

export interface RegrasParticipacao {
  vigencia_inicio: string;
  limite_captacao_pct: number;
  limite_performance_pct: number;
  limite_combo_pct: number;
  limites_temporais_anos: Record<string, number | string>;
  honorarios_aplicaveis: string;
  regra_alvara_indiscriminado: string;
  captacao_criterios: string;
  performance_criterios: string;
  excecoes: string;
  condicao_pagamento: string;
}

export async function getRegrasParticipacao() {
  return request<RegrasParticipacao>("/api/participacoes/regras");
}

export async function listParticipacoes(params?: {
  contract_id?: string;
  beneficiario_email?: string;
  apenas_ativos?: boolean;
}) {
  const qs = new URLSearchParams();
  if (params?.contract_id) qs.set("contract_id", params.contract_id);
  if (params?.beneficiario_email) qs.set("beneficiario_email", params.beneficiario_email);
  if (params?.apenas_ativos) qs.set("apenas_ativos", "true");
  const query = qs.toString();
  return request<{ participacoes: Participacao[]; total: number }>(
    `/api/participacoes${query ? `?${query}` : ""}`
  );
}

export async function createParticipacao(body: {
  contract_id: string;
  beneficiario_email: string;
  beneficiario_nome: string;
  tipo_honorario: string;
  percentual_captacao: number;
  percentual_performance: number;
  motivo_captacao?: string;
  motivo_performance?: string;
  natureza: string;
  cliente_cpf_cnpj?: string;
  data_inicio: string;
  aprovado_por?: string;
  observacoes?: string;
}) {
  return request<Participacao>("/api/participacoes", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getResumoParticipacao(pid: number) {
  return request<ResumoParticipacao>(`/api/participacoes/${pid}/resumo`);
}

export async function registrarPagamento(
  pid: number,
  body: {
    data_recebimento: string;
    valor_bruto: number;
    discriminado: boolean;
    valor_contratual?: number;
    observacoes?: string;
    status?: PagamentoStatus;
    parcela_num?: number;
    parcela_total?: number;
    nf_referencia?: string;
    tax_code_id?: number;
    tipo_cobranca?: string;
    natureza_pagamento?: string;
    tipo_documento?: string;
  }
) {
  return request<Pagamento>(`/api/participacoes/${pid}/pagamentos`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function atualizarStatusPagamento(pag_id: number, status: PagamentoStatus) {
  return request<Pagamento>(`/api/participacoes/pagamentos/${pag_id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function encerrarVinculo(pid: number, data_fim: string) {
  return request<Participacao>(
    `/api/participacoes/${pid}/encerrar-vinculo?data_fim=${encodeURIComponent(data_fim)}`,
    { method: "POST" }
  );
}

export interface ContratoPendente {
  contract_id: string;
  status: string;
  client_name: string;
  client_email: string;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  tem_rascunho: boolean;
  participacao_id: number | null;
  tipo_honorario_inferido: string | null;
  cliente_cpf_cnpj: string | null;
  percentual_captacao_rascunho?: number;
  percentual_performance_rascunho?: number;
  motivo_captacao_rascunho?: string | null;
  motivo_performance_rascunho?: string | null;
  beneficiario_email_rascunho?: string | null;
  beneficiario_nome_rascunho?: string | null;
  natureza_rascunho?: string | null;
  observacoes_rascunho?: string | null;
}

export async function listContratosPendentes(incluir_rascunhos = true) {
  return request<{ contratos: ContratoPendente[]; total: number }>(
    `/api/participacoes/contratos-pendentes?incluir_rascunhos=${incluir_rascunhos}`
  );
}

export async function aprovarParticipacao(
  pid: number,
  body: {
    percentual_captacao: number;
    percentual_performance: number;
    motivo_captacao?: string;
    motivo_performance?: string;
    tipo_honorario?: string;
    cliente_cpf_cnpj?: string;
    aprovado_por?: string;
    natureza?: string;
    observacoes?: string;
  }
) {
  return request<Participacao>(`/api/participacoes/${pid}/aprovar`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function simularParticipacao(body: {
  tipo_honorario: string;
  percentual_captacao: number;
  percentual_performance: number;
  data_inicio_participacao: string;
  data_recebimento: string;
  valor_liquido_recebido: number;
  vinculo_ativo: boolean;
  data_fim_vinculo?: string;
  eh_contratual: boolean;
}) {
  return request<{
    valor_participacao: number;
    dentro_limite_temporal: boolean;
    vinculo_ativo: boolean;
    motivo_zerado: string | null;
    percentual_aplicado: number;
  }>("/api/participacoes/simular", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function rollbackContract(contractId: string, version: number) {
  return request<{
    success: boolean;
    message: string;
    contract_id: string;
    version: number;
  }>(`/api/contracts/${contractId}/rollback?version=${version}`, {
    method: "POST",
  });
}
