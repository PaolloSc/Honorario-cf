import { limparCNPJ } from "./cnpj";
import type { Contratante, TipoPessoa } from "@/types/contract";
import { chamarApi, chamarApiJson, detalheDoErro, ErroApi, ConflitoError } from "./http";

// O transporte (base de URL, token, formato de erro) mora em ./http; reexportado para quem já importa daqui.
export {
  API_BASE,
  ConflitoError,
  ErroApi,
  SessaoExpiradaError,
  fetchAutenticado,
  garantirTokenValido,
  getAuthHeaders,
  setAccessToken,
} from "./http";

/** Chamada JSON padrão do wizard: 8s de limite, salvo quando quem chama passa o próprio signal. */
function request<T>(path: string, options?: RequestInit): Promise<T> {
  return chamarApiJson<T>(path, { ...options, timeoutMs: 8000 });
}

export interface ItemClausula {
  id: string; // chave fixa da cláusula (nunca o número)
  numero: string; // número que o Word mostra; só para a tela
  clausula: string;
  texto: string;
  padrao: string;
  ajustado: boolean;
  // Texto guardado do ajuste (mesmo pendente, para reaplicar); null se nao ha ajuste.
  ajuste: string | null;
  padrao_ajuste: string | null; // texto padrão da época em que o ajuste foi feito
  status: "ok" | "padrao_mudou" | null;
  editavel: boolean;
  etapa: number | null;
}

export interface AjusteDescartado {
  id: string;
  texto: string;
}

export interface PreviaTexto {
  preview_html: string;
  itens: ItemClausula[];
  ajustes_descartados: AjusteDescartado[];
}

// Previa + cláusulas ajustáveis, sem IA (usada ao salvar/desfazer um ajuste de texto).
export async function previewTexto(data: unknown) {
  return request<PreviaTexto>("/api/contract/preview-texto", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Varredura de portugues/padrao via DeepSeek antes de gerar o contrato definitivo.
// Chamada pode demorar (LLM) — usa timeout proprio, maior que o default de 8s.
export async function reviewContract(data: unknown) {
  return request<{
    enabled: boolean;
    findings: Array<{ trecho: string; problema: string; sugestao: string }>;
    preview_html?: string;
    itens?: ItemClausula[];
    ajustes_descartados?: AjusteDescartado[];
    error?: string;
  }>("/api/contract/review", {
    method: "POST",
    body: JSON.stringify(data),
    // Backend usa timeout=240s pra chamar a DeepSeek (thinking mode chegou a levar
    // 211s em teste real) — fica acima disso pra nao abortar antes.
    signal: AbortSignal.timeout(260000),
  });
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

// Contrato de consumidor/aereo: endpoint proprio, o de honorarios segue intacto.
export async function generateContratoConsumidor(data: unknown) {
  return request<{
    success: boolean;
    message: string;
    contract_id?: string;
    download_url?: string;
  }>("/api/contract/generate-consumidor", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Contrato de Ação de Consumo e' restrito a uma equipe (CONSUMIDOR_EMAILS no backend).
export async function podeUsarConsumidor() {
  return request<{ permitido: boolean }>("/api/contract/consumidor/acesso");
}

// Previa do contrato de consumidor antes de gravar: nada e' persistido.
export async function previewContratoConsumidor(data: unknown, signal?: AbortSignal) {
  const res = await chamarApi("/api/contract/preview-consumidor", {
    method: "POST",
    body: JSON.stringify(data),
    signal,
  });
  return res.text();
}

// Pop-up do wizard: como o trecho de honorários vai sair no contrato. Nada é gravado.
// Com revisar=true a IA corrige o português (lento): o html volta com o digitado
// riscado e a sugestão em verde.
export async function previewHonorarios(data: unknown, signal?: AbortSignal, revisar = false) {
  return chamarApiJson<{
    html: string;
    findings: Array<{ trecho: string; problema: string; sugestao: string }>;
    // Condição vaga/ambígua: só leitura, sem sugestão.
    avisos: Array<{ trecho: string; problema: string }>;
    erro?: string | null;
  }>("/api/contract/preview-honorarios", {
    method: "POST",
    body: JSON.stringify({ ...(data as object), revisar }),
    signal,
  });
}

export async function downloadContract(contractId: string) {
  const res = await chamarApi(`/api/contract/${contractId}/download`);
  return res.blob();
}

export async function previewContract(contractId: string) {
  const res = await chamarApi(`/api/contract/${contractId}/preview`);
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
  tem_participacao?: boolean;
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

export interface OabCadastro { numero: string; uf: string }

export interface ColaboradorWizard {
  name: string;
  email: string;
  role: string;
  oabs?: OabCadastro[];
}

export interface ConsultaProcesso {
  valido: boolean;
  numero: string;
  erro?: string;
  justica?: string;
  tribunal?: string | null;
  // Partes do Legal One do escritório (só leitura); null se o processo não está lá ou não há acesso.
  legalone: { cliente: string[]; contraria: string[]; descricao: string } | null;
}

export interface ProcessoPlanilha {
  linha: number;
  valido: boolean;
  numero: string;
  erro?: string;
  tribunal?: string | null;
  tipo: string;
  descricao: string;
  /** A descrição (partes) veio do Legal One, não da planilha. */
  partes_legalone?: boolean;
}

async function chamarProcessos<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    return await chamarApiJson<T>(path, { ...init, timeoutMs: 20000 });
  } catch (e) {
    // A tela de processos mostra só o `detail` do backend (ou um texto fixo).
    if (e instanceof ErroApi) throw new Error(detalheDoErro(e) ?? "Não foi possível concluir a consulta.");
    throw e;
  }
}

export const consultarProcesso = (numero: string) =>
  chamarProcessos<ConsultaProcesso>(`/api/processos/cnj?numero=${encodeURIComponent(numero)}`);

export function importarPlanilhaProcessos(arquivo: File) {
  const form = new FormData();
  form.append("arquivo", arquivo);
  return chamarProcessos<{ aviso: string; processos: ProcessoPlanilha[]; validos: number; invalidos: number }>(
    "/api/processos/planilha", { method: "POST", body: form });
}

export async function listColaboradores(opts?: { participavel?: boolean }) {
  const qs = opts?.participavel ? "?participavel=true" : "";
  return request<{ colaboradores: ColaboradorWizard[] }>(
    `/api/users/colaboradores${qs}`
  );
}

// Pergunta ao DocuSeal se todos ja' assinaram e conclui o contrato. O webhook
// e' o caminho normal, mas depende de configuracao externa; sem esta consulta o
// contrato ficava preso em "Enviado p/ Assinatura" mesmo com tudo assinado.
export async function sincronizarAssinatura(contractId: string) {
  return request<{
    contract_id: string;
    status: string;
    alterado: boolean;
    detalhe: string;
    pendentes: Array<{ role: string; name: string; email: string; link: string; whatsapp: string }>;
  }>(`/api/docuseal/${contractId}/sincronizar`, { method: "POST" });
}

export async function sendForSignature(data: {
  contract_id: string;
  signatarios: Array<{ email: string; name: string; role: string; phone?: string }>;
}) {
  return request<{
    success: boolean;
    message: string;
    // Contratantes com link e WhatsApp, para abrir o WhatsApp logo após o envio.
    whatsapp?: Array<{ role: string; name: string; email: string; link: string; whatsapp: string }>;
  }>(
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
  oabs?: OabCadastro[];
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
  body: { nome?: string; email?: string | null; papel?: string; ativo?: boolean; ordem?: number; oabs?: OabCadastro[] }
) {
  return request<Colaborador>(`/api/colaboradores/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteColaborador(id: number, hard = false) {
  return request<{ success: boolean; id: number; ativo?: boolean; deleted?: boolean }>(
    `/api/colaboradores/${id}${hard ? "?hard=true" : ""}`,
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

// QSA da Receita (só a BrasilAPI traz). Sugestão: não prova poder de representação.
export interface SocioReceita {
  nome: string;
  qualificacao: string;
}

export async function lookupCNPJ(cnpj: string) {
  const cnpjClean = limparCNPJ(cnpj);
  return request<{
    cnpj: string;
    razao_social: string;
    nome_fantasia: string;
    endereco: string;
    situacao_cadastral: string;
    socios?: SocioReceita[];
  }>(`/api/cnpj/${cnpjClean}`);
}

// ── Contracts Management ─────────────────────────────────────────

export interface ContractSummary {
  contract_id: string;
  status: string;
  client_name: string;
  client_email: string;
  tipo_contrato: string;
  contrato_origem_id?: string | null;
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
  tipo_contrato: string;
  contrato_origem_id?: string | null;
  socio_sugerido?: string | null;
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

// Versão que ESTA aba carregou de cada contrato: o PUT a devolve ao servidor, que recusa
// (409) se outra aba/pessoa já gravou uma versão mais nova.
const versaoCarregada: Record<string, number> = {};
export const EVENTO_VERSAO_DESATUALIZADA = "contrato-versao-desatualizada";

/** "Salvar sobre a versão atual": o próximo Salvar desta aba parte da versão que está no servidor. */
export function adotarVersaoAtual(contractId: string, versaoAtual: number) {
  versaoCarregada[contractId] = versaoAtual;
}

export async function getContractFormData(contractId: string, version?: number) {
  const qs = version ? `?version=${version}` : "";
  const r = await request<ContractFormDataResponse>(`/api/contracts/${contractId}/form-data${qs}`);
  if (!version) versaoCarregada[contractId] = r.version_number;
  return r;
}

export async function updateContract(contractId: string, formData: Record<string, unknown>) {
  try {
    const r = await request<{
      success: boolean;
      message: string;
      contract_id: string;
      version: number;
      download_url: string;
    }>(`/api/contracts/${contractId}`, {
      method: "PUT",
      body: JSON.stringify({ form_data: formData, version: versaoCarregada[contractId] ?? null }),
    });
    versaoCarregada[contractId] = r.version;
    return r;
  } catch (e) {
    if (!(e instanceof ConflitoError)) throw e;
    let detail: { codigo?: string; motivo?: string; sugestao?: string; versao_atual?: number } = {};
    try {
      detail = JSON.parse(e.corpo).detail ?? {};
    } catch {
      /* mensagem sem JSON: cai no texto padrão */
    }
    if (detail.codigo === "versao_desatualizada") {
      // Nada foi gravado e a tela NÃO recarrega sozinha (o digitado seria perdido): o aviso
      // global (AvisoVersaoDesatualizada) oferece o botão "Recarregar".
      if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(EVENTO_VERSAO_DESATUALIZADA, { detail: { motivo: detail.motivo, contractId, versaoAtual: (detail as { versao_atual?: number }).versao_atual } }));
      throw new Error(`${detail.motivo ?? "Este contrato foi alterado em outra aba."} Nada foi salvo; o que você digitou continua na tela.`);
    }
    if (detail.codigo === "contrato_travado") throw new Error(`${detail.motivo} ${detail.sugestao ?? ""}`.trim());
    throw new Error("Não foi possível salvar: o contrato foi alterado por outra pessoa ou está travado. Recarregue a página e tente de novo.");
  }
}

/** Arquiva a assinatura no DocuSeal e volta o contrato enviado a rascunho (nada muda se o DocuSeal falhar). */
export async function cancelarEnvioAssinatura(contractId: string) {
  return request<{ success: boolean; status: string }>(`/api/docuseal/${contractId}/cancelar-envio`, { method: "POST" });
}

export async function updateContractStatus(contractId: string, status: string) {
  return request<{ success: boolean; status: string }>(
    `/api/contracts/${contractId}/status?status=${encodeURIComponent(status)}`,
    { method: "PATCH" }
  );
}

// ── Rascunhos do wizard (autosave) ───────────────────────────────

export interface DraftSummary {
  draft_id: string;
  client_name: string;
  current_step: number;
  created_at: string;
  updated_at: string;
  expires_at: string; // quando a limpeza automática apaga, se ninguém mexer
}

export interface DraftDetail extends DraftSummary {
  form_data: Record<string, unknown>;
}

export interface SugestaoCliente {
  documento: string;
  nome: string;
  data_contrato: string;
  contratante: Partial<Contratante> & { tipo: TipoPessoa };
}

// Clientes de contratos já gerados por qualquer advogado (só a qualificação).
export async function sugerirClientes(q: string, signal?: AbortSignal) {
  return request<{ sugestoes: SugestaoCliente[] }>(
    `/api/clientes/sugestoes?q=${encodeURIComponent(q)}`,
    { signal }
  );
}

export async function listDrafts() {
  return request<{ drafts: DraftSummary[] }>("/api/drafts");
}

export async function getDraft(draftId: string) {
  return request<DraftDetail>(`/api/drafts/${encodeURIComponent(draftId)}`);
}

// keepalive deixa o PUT terminar mesmo se a aba fechar logo em seguida (limite ~64KB
// do navegador; acima disso o fetch falha e o salvamento normal já cobriu).
export async function saveDraft(
  draftId: string,
  formData: Record<string, unknown>,
  currentStep: number,
  opts?: { keepalive?: boolean; knownUpdatedAt?: string | null }
) {
  // knownUpdatedAt: versão que esta aba conhece; se outra gravou depois, vem ConflitoError
  return request<DraftSummary>(`/api/drafts/${encodeURIComponent(draftId)}`, {
    method: "PUT",
    body: JSON.stringify({
      form_data: formData,
      current_step: currentStep,
      known_updated_at: opts?.knownUpdatedAt ?? null,
    }),
    keepalive: opts?.keepalive,
  });
}

export async function deleteDraft(draftId: string) {
  return request<{ success: boolean }>(`/api/drafts/${encodeURIComponent(draftId)}`, {
    method: "DELETE",
  });
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

// ── Documentos complementares (aditivo, distrato, substabelecimento) ─────

export interface PrefillDocumento {
  contratantes: Array<Record<string, unknown>>;
  aditivos_existentes: number;
  data_contrato_origem: string | null;
  status_origem: string;
  /** Algum escopo do contrato de origem tem honorário de êxito. */
  origem_tem_exito?: boolean;
  aviso: string | null;
}

export interface DocumentoDerivado {
  contract_id: string;
  tipo_contrato: string;
  status: string;
  client_name: string;
  created_at: string;
}

export async function prefillDocumento(origemId: string) {
  return request<PrefillDocumento>(`/api/documentos/prefill/${origemId}`);
}

export async function listDocumentos(contractId: string) {
  return request<{ documentos: DocumentoDerivado[] }>(`/api/contracts/${contractId}/documentos`);
}

// Previa: nada e' gravado. Erro volta como ErroApi ("API error NNN: corpo"; o corpo traz os 422 por campo).
export async function previewDocumento(tipo: string, payload: unknown, signal?: AbortSignal) {
  const res = await chamarApi(`/api/documentos/${tipo}/preview`, {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
  return res.text();
}

export interface SubstabelecimentoExistente {
  existe: boolean;
  contract_id?: string;
  client_name?: string;
  status?: string;
  pode_acrescentar?: boolean;
  motivo?: string | null;
  processos?: string[];
  substabelecentes?: Array<{ nome: string; email: string; oab: string }>;
  substabelecidos?: Array<{ nome: string; oab: string }>;
  endereco_substabelecidos?: string;
}

// O cliente (CPF/CNPJ) já tem substabelecimento? Orienta "acrescentar o processo" ou "criar novo".
export async function substabelecimentoExistente(documento: string) {
  return request<SubstabelecimentoExistente>(
    `/api/documentos/substabelecimento-existente?documento=${encodeURIComponent(documento)}`,
  );
}

// acrescentarA: contract_id de um substabelecimento do mesmo outorgante, que recebe os processos.
export async function gerarDocumento(tipo: string, payload: unknown, acrescentarA?: string) {
  return request<{
    success: boolean;
    message: string;
    contract_id: string;
    download_url: string;
    aviso: string | null;
    acrescentado?: boolean;
  }>(`/api/documentos/${tipo}${acrescentarA ? `?acrescentar_a=${encodeURIComponent(acrescentarA)}` : ""}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
