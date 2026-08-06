from __future__ import annotations
 
from enum import Enum
from typing import Optional
 
from pydantic import BaseModel, Field, model_validator
 
 
class TipoPessoa(str, Enum):
    PF = "PF"
    PJ = "PJ"
 
 
class EstadoCivil(str, Enum):
    SOLTEIRO = "Solteiro(a)"
    CASADO = "Casado(a)"
    DIVORCIADO = "Divorciado(a)"
    VIUVO = "Viúvo(a)"
    UNIAO_ESTAVEL = "União Estável"
    SEPARADO = "Separado(a)"
 
 
class ContratantePF(BaseModel):
    tipo: TipoPessoa = TipoPessoa.PF
    nome: str
    nacionalidade: str
    cpf: str
    profissao: str
    estado_civil: EstadoCivil
    endereco: str
    email: str
 
 
class ContratantePJ(BaseModel):
    tipo: TipoPessoa = TipoPessoa.PJ
    cnpj: str
    razao_social: str = ""
    endereco: str = ""
    email: str
    representante_nome: Optional[str] = None
    representante_nacionalidade: Optional[str] = None
    representante_cpf: Optional[str] = None
    representante_profissao: Optional[str] = None
    representante_estado_civil: Optional[EstadoCivil] = None
    representante_email: Optional[str] = None
    representante_endereco: Optional[str] = None
 
 
class TipoEscopo(str, Enum):
    CONSULTORIA_CONTENCIOSO_GERAL = "consultoria_contencioso_geral"
    CONTENCIOSO_REPRESENTACAO = "contencioso_representacao"
    CONTENCIOSO_MEMORIAIS = "contencioso_memoriais"
    CONTENCIOSO_TUTELA_URGENCIA = "contencioso_tutela_urgencia"
    CONSULTORIA_LGPD = "consultoria_lgpd"
    CONSULTORIA_COMPLIANCE_TRABALHISTA = "consultoria_compliance_trabalhista"
    CONSULTORIA_PLANEJAMENTO_TRIBUTARIO = "consultoria_planejamento_tributario"
    CONSULTORIA_DIAGNOSTICO_FISCAL = "consultoria_diagnostico_fiscal"
    CONSULTORIA_PLANEJAMENTO_PATRIMONIAL = "consultoria_planejamento_patrimonial"
    CONSULTORIA_ESTRUTURACAO_SOCIETARIA = "consultoria_estruturacao_societaria"
    CONSULTORIA_CONTRATUAL = "consultoria_contratual"
    CONSULTORIA_ELABORACAO_DOCUMENTOS = "consultoria_elaboracao_documentos"
    CONSULTORIA_OPINIAO_LEGAL = "consultoria_opiniao_legal"
    OUTRO = "outro"
 
 
ESCOPO_LABELS: dict[TipoEscopo, str] = {
    TipoEscopo.CONSULTORIA_CONTENCIOSO_GERAL: "Consultoria e contencioso nas áreas de atuação do C&F",
    TipoEscopo.CONTENCIOSO_REPRESENTACAO: "Contencioso para representação e atuação em autos específicos ou ajuizamento de demandas",
    TipoEscopo.CONTENCIOSO_MEMORIAIS: "Contencioso para análise processual, elaboração e despacho de Memoriais e sustentação oral",
    TipoEscopo.CONTENCIOSO_TUTELA_URGENCIA: "Contencioso para análise processual e despacho de tutela de urgência",
    TipoEscopo.CONSULTORIA_LGPD: "Consultoria para implementação de diretrizes da Lei Geral de Proteção de Dados",
    TipoEscopo.CONSULTORIA_COMPLIANCE_TRABALHISTA: "Consultoria para implementação de diretrizes de Compliance Trabalhista",
    TipoEscopo.CONSULTORIA_PLANEJAMENTO_TRIBUTARIO: "Consultoria para planejamento tributário",
    TipoEscopo.CONSULTORIA_DIAGNOSTICO_FISCAL: "Consultoria de diagnóstico fiscal com eventual identificação e orientações para aproveitamento de créditos fiscais",
    TipoEscopo.CONSULTORIA_PLANEJAMENTO_PATRIMONIAL: "Consultoria para estruturação de planejamento patrimonial sucessório",
    TipoEscopo.CONSULTORIA_ESTRUTURACAO_SOCIETARIA: "Consultoria para (re)estruturação societária",
    TipoEscopo.CONSULTORIA_CONTRATUAL: "Consultoria para análise, revisão e negociação contratual",
    TipoEscopo.CONSULTORIA_ELABORACAO_DOCUMENTOS: "Consultoria para elaboração de documentos",
    TipoEscopo.CONSULTORIA_OPINIAO_LEGAL: "Consultoria para emissão de opinião legal (ou parecer)",
    TipoEscopo.OUTRO: "Outro escopo",
}
 
 
class TipoHonorario(str, Enum):
    HORA_TRABALHADA = "hora_trabalhada"
    PRO_LABORE = "pro_labore"
    MENSALIDADE = "mensalidade"
    EXITO = "exito"
    PERMUTA = "permuta"
 
 
class SubtipoMensalidade(str, Enum):
    ADVOCACIA_PARTIDO = "advocacia_partido"
    POR_PROCESSO = "por_processo"
    POR_PASTA = "por_pasta"
 
 
class VariacaoPrecoMensalidade(str, Enum):
    SEM_VARIACAO = "sem_variacao"
    LIMITACAO_TEMPORAL = "limitacao_temporal"
    REDUCAO_VOLUME = "reducao_volume"
    VARIACAO_FASE_PROCESSUAL = "variacao_fase_processual"
 
 
class SubtipoMemoriais(BaseModel):
    elaboracao_memoriais: bool = False
    despacho_memoriais: bool = False
    sustentacao_oral_relator: bool = False
    sustentacao_oral_todos_julgadores: bool = False
 
 
class HoraTrabalhada(BaseModel):
    valor_hora: float
    tem_teto_mensal: bool = False
    valor_teto_mensal: Optional[float] = None
    tem_pacote_horas: bool = False
    quantidade_horas_pacote: Optional[int] = None
    valor_pacote: Optional[float] = None
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    duracao_meses: Optional[int] = None
    horas_contratadas: Optional[float] = None
    horas_trabalhadas: Optional[float] = None
    tem_hora_urgencia: bool = True
    tem_hora_fora_expediente: bool = True
 
 
class ProLabore(BaseModel):
    valor_total: float
    tem_parcelamento: bool = False
    numero_parcelas: Optional[int] = None
    valor_parcela: Optional[float] = None
    vencimento: Optional[str] = None
    vencimento_data: Optional[str] = None
    vencimento_obs: Optional[str] = None
    vencimento_parcelas: Optional[str] = None
    vencimento_parcelas_data: Optional[str] = None
    vencimento_parcelas_obs: Optional[str] = None
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    duracao_meses: Optional[int] = None
 
 
class Mensalidade(BaseModel):
    valor: float
    subtipo: SubtipoMensalidade
    dia_vencimento: str
    dia_vencimento_data: Optional[str] = None
    dia_vencimento_obs: Optional[str] = None
    variacao_preco: VariacaoPrecoMensalidade = VariacaoPrecoMensalidade.SEM_VARIACAO
    limitacao_temporal_anos: Optional[int] = None
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    duracao_meses: Optional[int] = None
    faixas_preco: Optional[list[dict[str, str]]] = None
    fases_processuais: Optional[list[dict[str, str]]] = None
 
 
class SubtipoExito(str, Enum):
    PERCENTUAL_FIXO = "percentual_fixo"
    PERCENTUAL_VARIAVEL = "percentual_variavel"
 
 
class Exito(BaseModel):
    subtipo: SubtipoExito = SubtipoExito.PERCENTUAL_FIXO
    percentual: Optional[float] = None
    incidencia: str = ""
    base_calculo: str = ""
    vencimento: str = ""
    vencimento_data: Optional[str] = None
    vencimento_obs: Optional[str] = None
    forma_pagamento: str = ""
    numero_parcelas: Optional[int] = None
    valor_parcela: Optional[float] = None
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    duracao_meses: Optional[int] = None
    tem_beneficio_prospectivo: bool = False
    prospectivo_data_inicio: Optional[str] = None
    prospectivo_data_fim: Optional[str] = None
    prospectivo_duracao_meses: Optional[int] = None
    faixas_percentual: Optional[list[dict[str, str]]] = None
    deduz_outro_honorario: bool = False
    honorario_deduzido: Optional[str] = None
 
 
class Permuta(BaseModel):
    objeto_permuta: str
    descricao: str = ""
    tem_torna: bool = False
    valor_torna: Optional[float] = None
    forma_pagamento_torna: Optional[str] = None
 
 
class EscopoItem(BaseModel):
    tipo: TipoEscopo
    descricao_custom: Optional[str] = None
    numero_autos: Optional[str] = None
    demandas: Optional[str] = None
    pessoas_patrimonios: Optional[str] = None
    tipo_reestruturacao: Optional[str] = None
    documentos: Optional[str] = None
    consulta: Optional[str] = None
    subtipo_memoriais: Optional[SubtipoMemoriais] = None
    honorarios: list[TipoHonorario] = Field(default_factory=list)
    hora_trabalhada: Optional[HoraTrabalhada] = None
    pro_labore: Optional[ProLabore] = None
    mensalidade: Optional[Mensalidade] = None
    exito: Optional[Exito] = None
    permuta: Optional[Permuta] = None
 
 
class Acessorios(BaseModel):
    tem_reembolso: bool = True
    reembolso_limitado: bool = False
    descricao_limitacao_reembolso: Optional[str] = None
    tem_penalidade_inadimplemento: bool = True
    valor_diligencia: Optional[float] = None
    valor_km: Optional[float] = None
    criterio_extincao_exito: Optional[str] = None
    clausulas_adicionais: Optional[str] = None
 
 
class Participacao(BaseModel):
    tem_participacao: bool = False
    # Valor (tipo + campo do tipo escolhido)
    valor_tipo: Optional[str] = None  # "percentual" | "valor" | "outro"
    valor_percentual: Optional[str] = None
    valor_monetario: Optional[float] = None
    valor_outro: Optional[str] = None
    # Advogados
    para_quem: list[str] = []
    natureza: Optional[str] = None
    responsavel_captacao: Optional[str] = None
    responsavel_gestao: Optional[str] = None
    # Contato financeiro do cliente (3 campos)
    contato_financeiro_nome: Optional[str] = None
    contato_financeiro_email: Optional[str] = None
    contato_financeiro_telefone: Optional[str] = None
    # Cadastro no Legal One (independe de haver participacao)
    categoria_cliente: Optional[str] = None
    etiquetas: list[str] = []
    listas_transmissao: list[str] = []
    # Base da participacao (escopo ou honorario)
    base_tipo: Optional[str] = None  # "escopo" | "honorario"
    base_escopo_index: Optional[int] = None
    base_honorario: Optional[str] = None
    base_label: Optional[str] = None
    # Legados (compat com contratos salvos antes desta mudanca)
    percentual_ou_valor: Optional[str] = None
    contato_financeiro_cliente: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_and_migrate(cls, data):
        if not isinstance(data, dict):
            return data
        for field in ("natureza", "responsavel_captacao", "responsavel_gestao",
                      "valor_percentual", "valor_outro", "percentual_ou_valor",
                      "contato_financeiro_nome", "contato_financeiro_email",
                      "contato_financeiro_telefone", "contato_financeiro_cliente",
                      "categoria_cliente"):
            if data.get(field) is None:
                data[field] = ""
        for field in ("para_quem", "etiquetas", "listas_transmissao"):
            v = data.get(field)
            if isinstance(v, str):
                data[field] = [v] if v.strip() else []
            elif v is None:
                data[field] = []
        if not data.get("valor_tipo") and data.get("percentual_ou_valor"):
            data["valor_tipo"] = "outro"
            if not data.get("valor_outro"):
                data["valor_outro"] = data["percentual_ou_valor"]
        return data
 
 
class ContratoRequest(BaseModel):
    contratantes: list[ContratantePF | ContratantePJ]
    incluir_partes_relacionadas: bool = False
    escopos: list[EscopoItem]
    acessorios: Acessorios
    participacao: Participacao
    email_destinatario: Optional[str] = None
 
 
class ContratoResponse(BaseModel):
    success: bool
    message: str
    contract_id: Optional[str] = None
    download_url: Optional[str] = None
 
 
class EmailRequest(BaseModel):
    contract_id: str
    destinatario_email: str
    destinatario_nome: str
    assunto: Optional[str] = "Contrato de Honorários - C&F Advogados"
 
 
class DocuSealRequest(BaseModel):
    contract_id: str
    signatarios: list[dict[str, str]]
