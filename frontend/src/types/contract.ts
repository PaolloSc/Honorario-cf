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
  periodo_banco_horas_meses?: number;
  tem_hora_urgencia: boolean;
  tem_hora_fora_expediente: boolean;
}
 
export interface ProLabore {
  valor_total: number;
  tem_parcelamento: boolean;
  numero_parcelas?: number;
  valor_parcela?: number;
  vencimento?: string;
  vencimento_parcelas?: string;
}
 
export interface Mensalidade {
  valor: number;
  subtipo: SubtipoMensalidade;
  dia_vencimento: string;
  variacao_preco: VariacaoPrecoMensalidade;
  limitacao_temporal_anos?: number;
  faixas_preco?: Array<{ faixa: string; valor: string }>;
  fases_processuais?: Array<{ fase: string; valor: string }>;
}
 
export interface Exito {
  subtipo: SubtipoExito;
  percentual?: number;
  incidencia: string;
  base_calculo: string;
  vencimento: string;
  forma_pagamento: string;
  numero_parcelas?: number;
  valor_parcela?: number;
  tem_beneficio_prospectivo: boolean;
  periodo_prospectivo_meses?: number;
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
 
export interface Participacao {
  tem_participacao: boolean;
  percentual_ou_valor?: string;
  para_quem?: string;
  natureza?: string;
  responsavel_captacao?: string;
  responsavel_gestao?: string;
  contato_financeiro_cliente?: string;
}
 
export interface ContratoFormData {
  contratantes: Contratante[];
  incluir_partes_relacionadas: boolean;
  escopos: EscopoItem[];
  acessorios: Acessorios;
  participacao: Participacao;
  email_destinatario?: string;
}
 
export interface ContratoResponse {
  success: boolean;
  message: string;
  contract_id?: string;
  download_url?: string;
}
