import type {
  Acessorios,
  Contratante,
  ContratantePF,
  ContratantePJ,
  ContratoFormData,
  EnvioSalvo,
  Participacao,
} from "@/types/contract";

// Estado do wizard: os Dados do contrato têm UMA fonte (ver GLOSSARY.md e docs/adr/0001).
// As etapas leem daqui e escrevem aqui; este módulo é puro (sem React, sem rede) e é o seam dos testes.

/**
 * Versão do formato dos Dados do contrato (docs/adr/0002). Ausente = formato 1 (anterior ao
 * número). Ao mudar o formato: some 1, converta em normalizarFormData e cubra no .check.ts.
 */
export const VERSAO_FORMATO = 2;

export const DADOS_INICIAIS: ContratoFormData = {
  versao_formato: VERSAO_FORMATO,
  contratantes: [
    {
      tipo: "PF",
      nome: "",
      nacionalidade: "Brasileiro(a)",
      cpf: "",
      profissao: "",
      estado_civil: "Solteiro(a)",
      endereco: "",
      email: "",
    },
  ],
  incluir_partes_relacionadas: false,
  escopos: [],
  acessorios: {
    tem_reembolso: true,
    reembolso_limitado: false,
    tem_penalidade_inadimplemento: true,
  },
  participacao: {
    tem_participacao: false,
  },
};

// A vigência morava no pró-labore; contratos antigos a trazem de lá. A migração
// é só aqui (ao abrir no wizard): no backend ela ressuscitaria a vigência que o
// advogado apagou, e o .docx de um contrato antigo regenerado ganharia cláusula.
function vigencia(data: Partial<ContratoFormData>): Pick<Acessorios, "vigencia_inicio" | "vigencia_fim" | "vigencia_meses"> {
  const ac = data.acessorios;
  if (ac?.vigencia_inicio) {
    return { vigencia_inicio: ac.vigencia_inicio, vigencia_fim: ac.vigencia_fim, vigencia_meses: ac.vigencia_meses };
  }
  const pl = data.escopos?.find((e) => e.pro_labore?.data_inicio)?.pro_labore;
  return { vigencia_inicio: pl?.data_inicio, vigencia_fim: pl?.data_fim, vigencia_meses: pl?.duracao_meses };
}

// Ficha interna: aceita lista, string legada ou ausência — contratos antigos gravaram string.
function lista(v: unknown): string[] {
  return Array.isArray(v) ? v : typeof v === "string" && v.trim() ? [v] : [];
}

function fichaInterna(dados: unknown): Participacao {
  const p = (dados ?? {}) as any;
  let valorTipo = p.valor_tipo;
  let valorOutro = p.valor_outro ?? "";
  if (!valorTipo && p.percentual_ou_valor) {
    valorTipo = "outro";
    valorOutro = p.percentual_ou_valor;
  }
  // Contratos antigos gravaram para_quem (lista de nomes) + uma natureza única —
  // migra para participantes (cada advogado com natureza/percentual próprios).
  const participantes =
    Array.isArray(p.participantes) && p.participantes.length
      ? p.participantes
      : lista(p.para_quem).map((nome) => ({
          nome,
          natureza: p.natureza ?? "",
          percentual: p.valor_percentual,
        }));
  // Campos que o wizard não conhece (o backend pode estar à frente) passam adiante; só o formato
  // antigo, já convertido em participantes/valor_outro, sai.
  const { para_quem: _pq, natureza: _nat, percentual_ou_valor: _pov, ...desconhecidos } = p;
  return {
    ...desconhecidos,
    tem_participacao: p.tem_participacao ?? false,
    valor_tipo: valorTipo,
    valor_percentual: p.valor_percentual ?? "",
    valor_monetario: p.valor_monetario,
    valor_outro: valorOutro,
    participantes,
    responsavel_captacao: p.responsavel_captacao ?? "",
    responsavel_gestao: p.responsavel_gestao ?? "",
    contato_financeiro_nome: p.contato_financeiro_nome ?? "",
    contato_financeiro_email: p.contato_financeiro_email ?? "",
    contato_financeiro_telefone: p.contato_financeiro_telefone ?? "",
    categoria_cliente: p.categoria_cliente ?? "",
    etiquetas: lista(p.etiquetas),
    listas_transmissao: lista(p.listas_transmissao),
    // Sem estes a base da participação sumia ao reabrir o contrato para edição.
    base_tipo: p.base_tipo,
    base_escopo_index: p.base_escopo_index,
    base_honorario: p.base_honorario,
    base_label: p.base_label ?? "",
  };
}

/**
 * Abre Dados do contrato de qualquer formato conhecido (rascunho, contrato salvo, modelo) e devolve
 * o formato atual. Pura e idempotente: é a mesma conversão que o script do banco vai usar.
 */
export function normalizarFormData(data: Partial<ContratoFormData> | null | undefined): ContratoFormData {
  if (!data) return { ...DADOS_INICIAIS };

  return {
    ...data, // campos de topo que o wizard não conhece sobrevivem
    // Formato futuro (versão maior que a conhecida) não é rebaixado em silêncio.
    versao_formato: Math.max(data.versao_formato ?? 0, VERSAO_FORMATO),
    contratantes: data.contratantes?.length ? data.contratantes : DADOS_INICIAIS.contratantes,
    incluir_partes_relacionadas: data.incluir_partes_relacionadas ?? false,
    escopos: (data.escopos ?? []).map((e) =>
      e.pro_labore?.data_inicio || e.pro_labore?.data_fim || e.pro_labore?.duracao_meses
        ? { ...e, pro_labore: { ...e.pro_labore, data_inicio: undefined, data_fim: undefined, duracao_meses: undefined } }
        : e
    ),
    acessorios: {
      ...data.acessorios,
      tem_reembolso: data.acessorios?.tem_reembolso ?? true,
      reembolso_limitado: data.acessorios?.reembolso_limitado ?? false,
      descricao_limitacao_reembolso: data.acessorios?.descricao_limitacao_reembolso,
      tem_penalidade_inadimplemento: data.acessorios?.tem_penalidade_inadimplemento ?? true,
      valor_diligencia: data.acessorios?.valor_diligencia,
      valor_km: data.acessorios?.valor_km,
      criterio_extincao_exito: data.acessorios?.criterio_extincao_exito,
      clausulas_adicionais: data.acessorios?.clausulas_adicionais,
      ...vigencia(data),
    },
    participacao: fichaInterna(data.participacao),
    email_destinatario: data.email_destinatario,
    // Cláusulas reescritas na etapa 7: sem isto sumiam ao reabrir rascunho/contrato.
    ajustes_texto: data.ajustes_texto,
    envio: data.envio,
  };
}

// ── Envio (etapa 7) ───────────────────────────────────────────────────────

export function nomeDoContratante(c: Contratante): string {
  if (c.tipo === "PF") return (c as ContratantePF).nome;
  return (c as ContratantePJ).razao_social;
}

/** E-mails de envio: os do cadastro dos contratantes; o que o advogado editou vale se são os mesmos contratantes. */
export function destinatarios(data: ContratoFormData): Array<{ email: string; nome: string }> {
  const salvos = data.envio?.recipients;
  const mesmos = salvos?.length === data.contratantes.length;
  return data.contratantes.map((c, i) => ({
    email: (mesmos ? salvos![i]?.email : undefined) ?? c.email ?? "",
    nome: nomeDoContratante(c),
  }));
}

export interface Colaborador {
  name: string;
  email: string;
  role: string;
}

/**
 * Quem assina pelo escritório quando o advogado não escolheu: o responsável pela gestão, se for
 * sócio; senão o primeiro sócio entre os que recebem participação (regra do PR #74); senão o
 * único sócio cadastrado.
 */
export function sugerirSocio(data: ContratoFormData, colaboradores: Colaborador[]): string | undefined {
  const socios = colaboradores.filter((c) => c.role === "socio");
  const porNome = new Map(socios.map((s) => [s.name, s]));
  const candidatos = [data.participacao.responsavel_gestao, ...(data.participacao.participantes ?? []).map((p) => p.nome)];
  for (const nome of candidatos) {
    const socio = porNome.get((nome ?? "").trim());
    if (socio) return socio.email;
  }
  if (socios.length === 1 && socios[0].email) return socios[0].email;
  return undefined;
}

/**
 * Sócio que assina: o escolhido; se nunca escolheu (undefined), a sugestão. Esvaziar o campo de
 * propósito grava "" e fica vazio — não volta a sugerir.
 */
export function socioDoEnvio(data: ContratoFormData, colaboradores: Colaborador[]): string {
  const escolhido = data.envio?.socioEscritorio;
  if (escolhido !== undefined) return escolhido;
  return sugerirSocio(data, colaboradores) ?? "";
}

/** Grava escolhas do Envio. Só chamar por ação da pessoa: ler ou sugerir nunca altera os dados. */
export function alterarEnvio(data: ContratoFormData, patch: EnvioSalvo): ContratoFormData {
  return { ...data, envio: { ...(data.envio ?? {}), ...patch } };
}

// ── Ficha interna → financeiro ────────────────────────────────────────────

/**
 * A ficha vai ao financeiro quando há participação, cadastro do Legal One, contato financeiro ou
 * responsável pela gestão preenchidos — contratos sem participação também precisam ser lançados.
 */
export function temFichaParaFinanceiro(p?: Participacao): p is Participacao {
  if (!p) return false;
  return Boolean(
    p.tem_participacao ||
      p.categoria_cliente ||
      p.etiquetas?.length ||
      p.listas_transmissao?.length ||
      p.contato_financeiro_nome ||
      p.contato_financeiro_email ||
      p.contato_financeiro_telefone ||
      p.responsavel_gestao
  );
}

// Os campos de participação só entram no payload quando o toggle está ligado: o
// wizard preserva o que foi digitado antes de desligá-lo, e mandá-los assim faria o
// financeiro receber uma participação que o contrato não tem.
export function montarFicha(contractId: string, data: ContratoFormData, objetoContrato: string) {
  const p = data.participacao;
  return {
    contract_id: contractId,
    cliente_nome: nomeDoContratante(data.contratantes[0]),
    objeto_contrato: objetoContrato,
    categoria_cliente: p.categoria_cliente,
    etiquetas: p.etiquetas ?? [],
    listas_transmissao: p.listas_transmissao ?? [],
    // Contato financeiro do cliente e responsável pela gestão do contrato
    // independem de haver participação.
    contato_financeiro_nome: p.contato_financeiro_nome,
    contato_financeiro_email: p.contato_financeiro_email,
    contato_financeiro_telefone: p.contato_financeiro_telefone,
    responsavel_gestao: p.responsavel_gestao,
    ...(p.tem_participacao
      ? {
          valor_tipo: p.valor_tipo,
          valor_percentual: p.valor_percentual,
          valor_monetario: p.valor_monetario,
          valor_outro: p.valor_outro,
          participantes: p.participantes ?? [],
          responsavel_captacao: p.responsavel_captacao,
          base_tipo: p.base_tipo,
          base_escopo_index: p.base_escopo_index,
          base_honorario: p.base_honorario,
          base_label: p.base_label,
        }
      : {}),
  };
}
