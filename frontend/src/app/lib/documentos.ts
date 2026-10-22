// Regras puras dos documentos complementares (aditivo, distrato, substabelecimento), sem React
// nem rede. Verificadas em documentos.check.ts.

export type TipoDocumento = "aditivo" | "distrato" | "substabelecimento";
export const TIPOS_DOCUMENTO: TipoDocumento[] = ["aditivo", "distrato", "substabelecimento"];

export const ROTULO_TIPO: Record<TipoDocumento, string> = {
  aditivo: "Aditivo",
  distrato: "Distrato",
  substabelecimento: "Substabelecimento",
};

export function ehDocumentoComplementar(tipo: string | undefined | null): tipo is TipoDocumento {
  return !!tipo && (TIPOS_DOCUMENTO as string[]).includes(tipo);
}

// ── Estado dos formulários ────────────────────────────────────────────────

export interface Empresa { razao_social: string; cnpj: string }
export type TipoAlteracao = "alterar" | "excluir" | "adicionar";
export const ROTULO_ALTERACAO: Record<TipoAlteracao, string> = {
  alterar: "Alterar cláusula",
  excluir: "Excluir cláusula",
  adicionar: "Adicionar cláusula",
};
export interface Alteracao { tipo: TipoAlteracao; clausula: string; texto: string }
export const alteracaoVazia = (): Alteracao => ({ tipo: "alterar", clausula: "", texto: "" });
export interface AditivoForm {
  data_documento: string;
  data_contrato_origem: string;
  objeto: string;
  alteracoes: Alteracao[];
}
export interface DistratoForm extends PoderesForm {
  data_documento: string;
  data_contrato_origem: string;
  objeto_contrato_origem: string;
  ressalva_exito: boolean;
  substabelecer_e_devolver: boolean;
}
export const UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
  "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
];
export const OAB_UF_PADRAO = "MG";
/** OAB do formulario: so o numero e a UF (padrao MG); o texto do documento e' montado no envio. */
export interface Oab {
  numero: string;
  uf: string;
  /** Texto salvo que nao segue o padrao (varias OABs, formato livre): vai ao documento como esta, ate a pessoa editar. */
  original?: string;
}
export const oabVazia = (): Oab => ({ numero: "", uf: OAB_UF_PADRAO });

/** "36959" -> "36.959" (numeros so com digitos); inscricoes com letra ficam como digitadas. */
export function formatarOabNumero(valor: string): string {
  const comSufixo = valor.trim().match(/^([\d.]+)\s*-\s*([A-Za-z])$/); // "36959-a" -> "36.959-A"
  if (comSufixo) return `${formatarOabNumero(comSufixo[1])}-${comSufixo[2].toUpperCase()}`;
  const limpo = valor.replace(/[^0-9A-Za-z]/g, "").toUpperCase().slice(0, 8);
  return /^\d+$/.test(limpo) ? limpo.replace(/\B(?=(\d{3})+(?!\d))/g, ".") : limpo;
}

/** Texto da OAB no documento. Substabelecente: "OAB/MG n.º 36.959"; substabelecido: "OAB/MG sob o n.º 36.959". */
export function oabTexto(o: Oab, sob = false): string {
  if (o.original && o.numero === o.original.trim()) return o.original; // nunca reescreve o que nao entendeu
  return `OAB/${o.uf || OAB_UF_PADRAO} ${sob ? "sob o " : ""}n.º ${formatarOabNumero(o.numero)}`;
}

/** Troca a UF. Num texto "original" (fora do padrao) o numero nao e' aproveitavel com outra UF: limpa. */
export function trocarUfOab(o: Oab, uf: string): Oab {
  return o.original ? { numero: "", uf } : { ...o, uf };
}

/** Texto salvo ("OAB/MG nº 36.959", "OAB/SP sob o n.º 1.234") -> numero e UF do formulario. */
export function lerOab(texto: string | undefined | null): Oab {
  const t = (texto ?? "").trim();
  const numero = "([0-9][0-9.]*(?:\\s*-\\s*[A-Za-z])?)";
  // Padrao: "OAB/MG n.º 36.959", "OAB-SP 12345", "OAB/MG sob o n.º 1.234", com ou sem sufixo "-A".
  const m = t.match(new RegExp(`^OAB\\s*[/-]\\s*([A-Za-z]{2})\\s*(?:sob\\s+o\\s+)?(?:n\\s*\\.?\\s*[º°o]?\\s*\\.?\\s*)?${numero}$`, "i"));
  if (m) return { numero: formatarOabNumero(m[2]), uf: m[1].toUpperCase() };
  if (new RegExp(`^${numero}$`).test(t)) return { numero: formatarOabNumero(t), uf: OAB_UF_PADRAO };
  // Fora do padrao (varias OABs, texto livre): fica exatamente como esta.
  return t ? { numero: t, uf: OAB_UF_PADRAO, original: t } : { numero: "", uf: OAB_UF_PADRAO };
}

/** "36959/MG, 1234/SP" -> OABs do cadastro (numero so digitos, UF da lista); null se algum item for invalido. */
export function oabsDoTexto(texto: string): { numero: string; uf: string }[] | null {
  const itens = texto.split(/[,;]/).map((t) => t.trim()).filter(Boolean);
  const saida: { numero: string; uf: string }[] = [];
  for (const item of itens) {
    const m = item.match(/^([\d.]+)\s*\/\s*([A-Za-z]{2})$/);
    const numero = m ? m[1].replace(/\./g, "") : "";
    const uf = m ? m[2].toUpperCase() : "";
    if (!/^\d{1,7}$/.test(numero) || !UFS.includes(uf)) return null;
    saida.push({ numero, uf });
  }
  return saida;
}
export const oabsParaTexto = (oabs: { numero: string; uf: string }[]) => oabs.map((o) => `${o.numero}/${o.uf}`).join(", ");

export interface Substabelecente { nome: string; email: string; oab: Oab }
export interface Substabelecido { nome: string; oab: Oab }
export interface Processo { tipo: string; numero: string; descricao: string }
/** Quem assina, quem recebe os poderes e os processos: comum ao substabelecimento e ao distrato que o gera. */
export interface PoderesForm {
  substabelecentes: Substabelecente[];
  substabelecidos: Substabelecido[];
  endereco_substabelecidos: string;
  processos: Processo[];
}
export interface SubstabelecimentoForm extends PoderesForm {
  data_documento: string;
  outorgante_pj: boolean;
  outorgante_nome: string;
  outorgante_documento: string;
  substabelecentes: Substabelecente[];
  substabelecidos: Substabelecido[];
  endereco_substabelecidos: string;
  processos: Processo[];
}
export type EstadoDocumento = AditivoForm | DistratoForm | SubstabelecimentoForm;

export const processoVazio = (): Processo => ({ tipo: "Processo", numero: "", descricao: "" });
export const substabelecidoVazio = (): Substabelecido => ({ nome: "", oab: oabVazia() });

export function estadoInicial(tipo: TipoDocumento, hoje: string): EstadoDocumento {
  if (tipo === "aditivo") {
    return {
      data_documento: hoje, data_contrato_origem: "", objeto: "", alteracoes: [alteracaoVazia()],
    };
  }
  if (tipo === "distrato") {
    return {
      data_documento: hoje, data_contrato_origem: "", objeto_contrato_origem: "",
      ressalva_exito: true, substabelecer_e_devolver: false,
      substabelecentes: [], substabelecidos: [substabelecidoVazio()], endereco_substabelecidos: "",
      processos: [processoVazio()],
    };
  }
  return {
    data_documento: hoje, outorgante_pj: true, outorgante_nome: "", outorgante_documento: "",
    substabelecentes: [], substabelecidos: [substabelecidoVazio()], endereco_substabelecidos: "",
    processos: [processoVazio()],
  };
}

// ── Número CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO, DD = dígito verificador, módulo 97) ──

const CNJ = /^(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$/;

export function cnjValido(numero: string): boolean {
  const m = CNJ.exec((numero || "").trim());
  if (!m) return false;
  const [, seq, dv, ano, j, tr, origem] = m;
  // Resto por partes: o número inteiro (20 dígitos) não cabe num Number.
  let resto = 0;
  for (const ch of seq + ano + j + tr + origem + "00") resto = (resto * 10 + Number(ch)) % 97;
  return 98 - resto === Number(dv);
}

// ── Payload da API ────────────────────────────────────────────────────────

function payloadPoderes(e: PoderesForm) {
  return {
  substabelecentes: e.substabelecentes.map((s) => ({ nome: s.nome, email: s.email, oab: oabTexto(s.oab) })),
  substabelecidos: e.substabelecidos.map((s) => ({ nome: s.nome.trim(), oab: oabTexto(s.oab, true) })),
  endereco_substabelecidos: e.endereco_substabelecidos.trim(),
  processos: e.processos.map((p) => ({
    tipo: p.tipo.trim() || "Processo", numero: p.numero.trim(), descricao: p.descricao.trim(),
  })),
  };
}

export function montarPayload(
  tipo: TipoDocumento,
  estado: EstadoDocumento,
  origemId: string | null,
): Record<string, unknown> {
  const base = { contrato_origem_id: origemId, data_documento: estado.data_documento || null };
  if (tipo === "aditivo") {
    const e = estado as AditivoForm;
    return {
      ...base,
      data_contrato_origem: e.data_contrato_origem,
      objeto: e.objeto.trim(),
      alteracoes: e.alteracoes.map((a) => ({
        tipo: a.tipo,
        clausula: a.tipo === "adicionar" ? null : a.clausula.trim(),
        texto: a.tipo === "excluir" ? null : a.texto.trim(),
      })),
    };
  }
  if (tipo === "distrato") {
    const e = estado as DistratoForm;
    return {
      ...base,
      data_contrato_origem: e.data_contrato_origem,
      objeto_contrato_origem: e.objeto_contrato_origem.trim(),
      ressalva_exito: e.ressalva_exito,
      substabelecer_e_devolver: e.substabelecer_e_devolver,
      // O substabelecimento so vai junto quando a opcao esta marcada.
      substabelecimento: e.substabelecer_e_devolver ? payloadPoderes(e) : null,
    };
  }
  const e = estado as SubstabelecimentoForm;
  const nome = e.outorgante_nome.trim();
  const doc = e.outorgante_documento.trim();
  return {
    ...base,
    outorgante: e.outorgante_pj
      ? { razao_social: nome, cnpj: doc || null }
      : { nome, cpf: doc || null },
    ...payloadPoderes(e),
  };
}

// Salvos antes de 22/10/2026 trazem genero/estado civil: abrem sem eles (o texto salvo nao muda).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function poderesDoFormData(fd: Record<string, any>): PoderesForm {
  return {
    substabelecentes: (fd.substabelecentes ?? []).map((s: { nome: string; email: string; oab: string }) => ({
      nome: s.nome, email: s.email, oab: lerOab(s.oab),
    })),
    substabelecidos: (fd.substabelecidos?.length ? fd.substabelecidos : [{ nome: "", oab: "" }]).map((s: { nome: string; oab: string }) => ({
      nome: s.nome, oab: lerOab(s.oab),
    })),
    endereco_substabelecidos: fd.endereco_substabelecidos ?? "",
    processos: fd.processos?.length ? fd.processos : [processoVazio()],
  };
}

/** Form salvo (form_data da API) -> estado do formulário, para editar um rascunho. */
export function estadoDoFormData(tipo: TipoDocumento, fd: Record<string, any>, hoje: string): EstadoDocumento { // eslint-disable-line @typescript-eslint/no-explicit-any
  const base = estadoInicial(tipo, hoje);
  if (tipo === "aditivo") {
    return {
      ...(base as AditivoForm),
      data_documento: fd.data_documento ?? hoje,
      data_contrato_origem: fd.data_contrato_origem ?? "",
      objeto: fd.objeto ?? "",
      // Aditivo salvo com remuneracao/abrangencia (legado): abre sem alteracoes; o advogado lista as mudancas.
      alteracoes: (fd.alteracoes ?? []).map((x: Partial<Alteracao>) => ({
        tipo: x.tipo ?? "alterar", clausula: x.clausula ?? "", texto: x.texto ?? "",
      })),
    };
  }
  if (tipo === "distrato") {
    return {
      data_documento: fd.data_documento ?? hoje,
      data_contrato_origem: fd.data_contrato_origem ?? "",
      objeto_contrato_origem: fd.objeto_contrato_origem ?? "",
      ressalva_exito: !!fd.ressalva_exito,
      substabelecer_e_devolver: !!fd.substabelecer_e_devolver,
      ...poderesDoFormData(fd.substabelecimento ?? {}),
    };
  }
  const o = fd.outorgante ?? {};
  return {
    data_documento: fd.data_documento ?? hoje,
    outorgante_pj: !o.nome || !!o.razao_social,
    outorgante_nome: o.razao_social ?? o.nome ?? "",
    outorgante_documento: o.cnpj ?? o.cpf ?? "",
    ...poderesDoFormData(fd),
  };
}

// ── Validação no cliente (mesmas chaves dos erros 422 do backend) ─────────

export type Erros = Record<string, string>;

// cnpjOk vem de cnpj.ts (injetado para este arquivo rodar puro no node, sem extensão de import).
export function validar(tipo: TipoDocumento, estado: EstadoDocumento, cnpjOk: (c: string) => boolean): Erros {
  const e: Erros = {};
  const obrig = (chave: string, valor: string | undefined | null, msg = "Campo obrigatório") => {
    if (!valor || !String(valor).trim()) e[chave] = msg;
  };
  obrig("data_documento", estado.data_documento);
  const validarPoderes = (s: PoderesForm) => {
    if (!s.substabelecentes.length) e.substabelecentes = "Escolha ao menos um substabelecente";
    if (!s.substabelecidos.length) e.substabelecidos = "Informe ao menos um substabelecido";
    s.substabelecidos.forEach((x, i) => {
      obrig(`substabelecidos.${i}.nome`, x.nome);
      obrig(`substabelecidos.${i}.oab`, x.oab.numero);
    });
    s.substabelecentes.forEach((x, i) => obrig(`substabelecentes.${i}.oab`, x.oab.numero));
    if (!s.processos.length) e.processos = "Informe ao menos um processo";
    s.processos.forEach((p, i) => {
      if (!cnjValido(p.numero)) e[`processos.${i}.numero`] = "Número fora do padrão CNJ ou com dígito verificador errado";
    });
  };

  if (tipo === "aditivo") {
    const a = estado as AditivoForm;
    obrig("data_contrato_origem", a.data_contrato_origem);
    obrig("objeto", a.objeto);
    if (!a.alteracoes.length) e.alteracoes = "Inclua ao menos uma alteração";
    a.alteracoes.forEach((alt, i) => {
      if (alt.tipo !== "adicionar") obrig(`alteracoes.${i}.clausula`, alt.clausula, "Informe a cláusula do contrato original");
      if (alt.tipo !== "excluir") obrig(`alteracoes.${i}.texto`, alt.texto, "Informe o novo texto");
    });
  } else if (tipo === "distrato") {
    const d = estado as DistratoForm;
    obrig("data_contrato_origem", d.data_contrato_origem);
    obrig("objeto_contrato_origem", d.objeto_contrato_origem);
    if (d.substabelecer_e_devolver) validarPoderes(d);
  } else {
    const s = estado as SubstabelecimentoForm;
    obrig("outorgante", s.outorgante_nome, "Informe o outorgante");
    validarPoderes(s);
  }
  return e;
}

// ── Erros 422 da API em português, por campo ──────────────────────────────

interface Erro422 { loc?: (string | number)[]; msg?: string; type?: string }

const POR_TIPO: Record<string, string> = {
  missing: "Campo obrigatório",
  string_too_short: "Campo obrigatório",
  too_short: "Informe ao menos um item",
  greater_than: "Deve ser maior que zero",
  int_parsing: "Use um número inteiro",
  int_type: "Use um número inteiro",
  float_parsing: "Use um número",
  float_type: "Use um número",
  string_type: "Texto inválido",
  bool_parsing: "Valor inválido",
  literal_error: "Opção inválida",
  value_error: "",
};

export function traduzirErro(e: Erro422): string {
  const fixo = e.type ? POR_TIPO[e.type] : undefined;
  if (fixo) return fixo;
  // value_error: a mensagem já foi escrita em português no backend ("Value error, ...").
  return (e.msg ?? "Valor inválido").replace(/^Value error,\s*/i, "");
}

/** Resposta de erro da API ("422 {...}") -> mensagens por campo + avisos gerais. */
export function errosDaApi(erro: unknown): { campos: Erros; geral: string } {
  const bruto = erro instanceof Error ? erro.message : String(erro);
  const json = /\{[\s\S]*\}$/.exec(bruto);
  if (json) {
    try {
      const detail = JSON.parse(json[0]).detail;
      if (typeof detail === "string") return { campos: {}, geral: detail };
      if (Array.isArray(detail)) {
        const campos: Erros = {};
        const soltos: string[] = [];
        for (const d of detail as Erro422[]) {
          const loc = (d.loc ?? []).filter((x) => x !== "body");
          if (loc.length) campos[loc.join(".")] = traduzirErro(d);
          else soltos.push(traduzirErro(d));
        }
        return { campos, geral: soltos.join("; ") };
      }
    } catch {
      /* corpo não era JSON */
    }
  }
  return { campos: {}, geral: bruto };
}

// ── Lista de contratos: derivados logo abaixo do contrato de origem ───────

export interface ComOrigem { contract_id: string; contrato_origem_id?: string | null }

export function agruparDerivados<T extends ComOrigem>(itens: T[]): { item: T; derivado: boolean }[] {
  const ids = new Set(itens.map((i) => i.contract_id));
  const filhosDe = new Map<string, T[]>();
  for (const i of itens) {
    if (i.contrato_origem_id && ids.has(i.contrato_origem_id)) {
      filhosDe.set(i.contrato_origem_id, [...(filhosDe.get(i.contrato_origem_id) ?? []), i]);
    }
  }
  const saida: { item: T; derivado: boolean }[] = [];
  for (const i of itens) {
    if (i.contrato_origem_id && ids.has(i.contrato_origem_id)) continue; // entra sob o pai
    saida.push({ item: i, derivado: false });
    for (const f of filhosDe.get(i.contract_id) ?? []) saida.push({ item: f, derivado: true });
  }
  return saida;
}

