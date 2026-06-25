export type TipoPessoa = "PF" | "PJ";
 
export type EstadoCivil =
  | "Solteiro(a)"
  | "Casado(a)"
  | "Divorciado(a)"
  | "Viúvo(a)"
  | "União Estável"
  | "Separado(a)";
 
export interface ContratantePF {
  tipo: "PF";
  nome: string;
  nacionalidade: string;
  cpf: string;
  profissao: string;
  estado_civil: EstadoCivil;
  endereco: string;
  email: string;
}
 
export interface ContratantePJ {
  tipo: "PJ";
  cnpj: string;
  razao_social: string;
  endereco: string;
  email: string;
  representante_nome?: string;
  representante_nacionalidade?: string;
  representante_cpf?: string;
  representante_profissao?: string;
  representante_estado_civil?: EstadoCivil;
  representante_email?: string;
  representante_endereco?: string;
}
 
export type Contratante = ContratantePF | ContratantePJ;
 
export type TipoEscopo =
  | "consultoria_contencioso_geral"
  | "contencioso_representacao"
  | "contencioso_memoriais"
  | "contencioso_tutela_urgencia"
  | "consultoria_lgpd"
  | "consultoria_compliance_trabalhista"
  | "consultoria_planejamento_tributario"
  | "consultoria_diagnostico_fiscal"
  | "consultoria_planejamento_patrimonial"
  | "consultoria_estruturacao_societaria"
  | "consultoria_contratual"
  | "consultoria_elaboracao_documentos"
  | "consultoria_opiniao_legal"
  | "outro";
 
export const ESCOPO_LABELS: Record<TipoEscopo, string> = {
  consultoria_contencioso_geral:
    "Consultoria e contencioso nas áreas de atuação do C&F",
  contencioso_representacao:
    "Contencioso para representação e atuação em autos / ajuizamento de demandas",
  contencioso_memoriais:
    "Contencioso para análise processual, elaboração e despacho de Memoriais e sustentação oral",
  contencioso_tutela_urgencia:
    "Contencioso para análise processual e despacho de tutela de urgência",
  consultoria_lgpd:
    "Consultoria para implementação de diretrizes da LGPD",
  consultoria_compliance_trabalhista:
    "Consultoria para implementação de Compliance Trabalhista",
  consultoria_planejamento_tributario: "Consultoria para planejamento tributário",
  consultoria_diagnostico_fiscal:
    "Consultoria de diagnóstico fiscal com orientações para créditos fiscais",
  consultoria_planejamento_patrimonial:
    "Consultoria para planejamento patrimonial sucessório",
  consultoria_estruturacao_societaria:
    "Consultoria para (re)estruturação societária",
  consultoria_contratual:
    "Consultoria para análise, revisão e negociação contratual",
  consultoria_elaboracao_documentos: "Consultoria para elaboração de documentos",
  consultoria_opiniao_legal:
    "Consultoria para emissão de opinião legal (ou parecer)",
  outro: "Outro escopo (campo aberto)",
};
 
export type TipoHonorario =
  | "hora_trabalhada"
  | "pro_labore"
  | "mensalidade"
  | "exito"
  | "permuta";
 
export const HONORARIO_LABELS: Record<TipoHonorario, string> = {
  hora_trabalhada: "Hora Trabalhada",
  pro_labore: "Pró-labore",
  mensalidade: "Mensalidade",
  exito: "Êxito",
  permuta: "Permuta",
};

export type SubtipoMensalidade =
  | "advocacia_partido"
  | "por_processo"
  | "por_pasta";
 
export type VariacaoPrecoMensalidade =
  | "sem_variacao"
  | "limitacao_temporal"
  | "reducao_volume"
  | "variacao_fase_processual";
 
export type SubtipoExito = "percentual_fixo" | "percentual_variavel";
 
export interface SubtipoMemoriais {
  elaboracao_memoriais: boolean;
  despacho_memoriais: boolean;
  sustentacao_oral_relator: boolean;
  sustentacao_oral_todos_julgadores: boolean;
}
 
export interface HoraTrabalhada {
  valor_hora: number;
  tem_teto_mensal: boolean;
  valor_teto_mensal?: number;
  tem_pacote_horas: boolean;
  quantidade_horas_pacote?: number;
  valor_pacote?: number;
  data_inicio?: string;
  data_fim?: string;
  duracao_meses?: number;
  horas_contratadas?: number;
  horas_trabalhadas?: number;
  tem_hora_urgencia: boolean;
  tem_hora_fora_expediente: boolean;
}
 
export interface ProLabore {
  valor_total: number;
  tem_parcelamento: boolean;
  numero_parcelas?: number;
  valor_parcela?: number;
  vencimento?: string;
  vencimento_data?: string;
  vencimento_obs?: string;
  vencimento_parcelas?: string;
  vencimento_parcelas_data?: string;
  vencimento_parcelas_obs?: string;
  data_inicio?: string;
  data_fim?: string;
  duracao_meses?: number;
}
 
export interface Mensalidade {
  valor: number;
  subtipo: SubtipoMensalidade;
  dia_vencimento: string;
  dia_vencimento_data?: string;
  dia_vencimento_obs?: string;
  variacao_preco: VariacaoPrecoMensalidade;
  limitacao_temporal_anos?: number;
  data_inicio?: string;
  data_fim?: string;
  duracao_meses?: number;
  faixas_preco?: Array<{ faixa: string; valor: string }>;
  fases_processuais?: Array<{ fase: string; valor: string }>;
}
 
export interface Exito {
  subtipo: SubtipoExito;
  percentual?: number;
  incidencia: string;
  base_calculo: string;
  vencimento: string;
  vencimento_data?: string;
  vencimento_obs?: string;
  forma_pagamento: string;
  numero_parcelas?: number;
  valor_parcela?: number;
  data_inicio?: string;
  data_fim?: string;
  duracao_meses?: number;
  tem_beneficio_prospectivo: boolean;
  prospectivo_data_inicio?: string;
  prospectivo_data_fim?: string;
  prospectivo_duracao_meses?: number;
  faixas_percentual?: Array<{ faixa: string; percentual: string }>;
  deduz_outro_honorario: boolean;
  honorario_deduzido?: string;
}
 
export interface Permuta {
  objeto_permuta: string;
  descricao: string;
  tem_torna: boolean;
  valor_torna?: number;
  forma_pagamento_torna?: string;
}
 
export interface EscopoItem {
  tipo: TipoEscopo;
  descricao_custom?: string;
  numero_autos?: string;
  demandas?: string;
  pessoas_patrimonios?: string;
  tipo_reestruturacao?: string;
  documentos?: string;
  consulta?: string;
  subtipo_memoriais?: SubtipoMemoriais;
  honorarios: TipoHonorario[];
  hora_trabalhada?: HoraTrabalhada;
  pro_labore?: ProLabore;
  mensalidade?: Mensalidade;
  exito?: Exito;
  permuta?: Permuta;
}
 
export interface Acessorios {
  tem_reembolso: boolean;
  reembolso_limitado: boolean;
  descricao_limitacao_reembolso?: string;
  tem_penalidade_inadimplemento: boolean;
  valor_diligencia?: number;
}
 
export type ParticipacaoValorTipo = "percentual" | "valor" | "outro";

export interface Participacao {
  tem_participacao: boolean;
  valor_tipo?: ParticipacaoValorTipo;
  valor_percentual?: string;
  valor_monetario?: number;
  valor_outro?: string;
  para_quem?: string[];
  natureza?: string;
  responsavel_captacao?: string;
  responsavel_gestao?: string;
  contato_financeiro_nome?: string;
  contato_financeiro_email?: string;
  contato_financeiro_telefone?: string;
  base_tipo?: "escopo" | "honorario";
  base_escopo_index?: number;
  base_honorario?: TipoHonorario;
  base_label?: string;
  // legados (compat edição)
  percentual_ou_valor?: string;
  contato_financeiro_cliente?: string;
}
 
export interface ContratoFormData {
  contratantes: Contratante[];
  incluir_partes_relacionadas: boolean;
  escopos: EscopoItem[];
  acessorios: Acessorios;
  participacao: Participacao;
  email_destinatario?: string;
  testemunhas?: { nome: string; email: string }[];
}
 
export interface ContratoResponse {
  success: boolean;
  message: string;
  contract_id?: string;
  download_url?: string;
}
