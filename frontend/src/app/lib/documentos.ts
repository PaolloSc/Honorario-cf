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
export interface AditivoForm {
  data_documento: string;
  data_contrato_origem: string;
  objeto: string;
  valor_mensal?: number;
  franquia_horas: string; // texto do input; vazio = sem franquia
  valor_hora_excedente?: number;
  compensacao_anual: boolean;
  abrangencia: Empresa[];
}
export interface DistratoForm {
  data_documento: string;
  data_contrato_origem: string;
  objeto_contrato_origem: string;
  ressalva_exito: boolean;
  substabelecer_e_devolver: boolean;
}
export interface Substabelecente { nome: string; email: string; oab: string }
export interface Substabelecido { nome: string; genero: "F" | "M"; estado_civil: string; oab: string }
export interface Processo { tipo: string; numero: string; descricao: string }
export interface SubstabelecimentoForm {
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
export const substabelecidoVazio = (): Substabelecido => ({ nome: "", genero: "F", estado_civil: "", oab: "" });

export function estadoInicial(tipo: TipoDocumento, hoje: string): EstadoDocumento {
  if (tipo === "aditivo") {
    return {
      data_documento: hoje, data_contrato_origem: "", objeto: "", franquia_horas: "",
      compensacao_anual: false, abrangencia: [],
    };
  }
  if (tipo === "distrato") {
    return {
      data_documento: hoje, data_contrato_origem: "", objeto_contrato_origem: "",
      ressalva_exito: true, substabelecer_e_devolver: false,
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

export function montarPayload(
  tipo: TipoDocumento,
  estado: EstadoDocumento,
  origemId: string | null,
): Record<string, unknown> {
  const base = { contrato_origem_id: origemId, data_documento: estado.data_documento || null };
  if (tipo === "aditivo") {
    const e = estado as AditivoForm;
    const franquia = parseInt(e.franquia_horas, 10);
    return {
      ...base,
      data_contrato_origem: e.data_contrato_origem,
      objeto: e.objeto.trim(),
      remuneracao: {
        valor_mensal: e.valor_mensal ?? null,
        franquia_horas: Number.isFinite(franquia) && franquia > 0 ? franquia : null,
        valor_hora_excedente: e.valor_hora_excedente ?? null,
      },
      compensacao_anual: e.compensacao_anual,
      abrangencia: e.abrangencia.map((a) => ({ razao_social: a.razao_social.trim(), cnpj: a.cnpj.trim() })),
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
    substabelecentes: e.substabelecentes.map((s) => ({ nome: s.nome, email: s.email, oab: s.oab.trim() })),
    substabelecidos: e.substabelecidos.map((s) => ({
      nome: s.nome.trim(), genero: s.genero, estado_civil: s.estado_civil.trim(), oab: s.oab.trim(),
    })),
    endereco_substabelecidos: e.endereco_substabelecidos.trim(),
    processos: e.processos.map((p) => ({
      tipo: p.tipo.trim() || "Processo", numero: p.numero.trim(), descricao: p.descricao.trim(),
    })),
  };
}

/** Form salvo (form_data da API) -> estado do formulário, para editar um rascunho. */
export function estadoDoFormData(tipo: TipoDocumento, fd: Record<string, any>, hoje: string): EstadoDocumento { // eslint-disable-line @typescript-eslint/no-explicit-any
  const base = estadoInicial(tipo, hoje);
  if (tipo === "aditivo") {
    const r = fd.remuneracao ?? {};
    return {
      ...(base as AditivoForm),
      data_documento: fd.data_documento ?? hoje,
      data_contrato_origem: fd.data_contrato_origem ?? "",
      objeto: fd.objeto ?? "",
      valor_mensal: r.valor_mensal ?? undefined,
      franquia_horas: r.franquia_horas ? String(r.franquia_horas) : "",
      valor_hora_excedente: r.valor_hora_excedente ?? undefined,
      compensacao_anual: !!fd.compensacao_anual,
      abrangencia: fd.abrangencia ?? [],
    };
  }
  if (tipo === "distrato") {
    return {
      data_documento: fd.data_documento ?? hoje,
      data_contrato_origem: fd.data_contrato_origem ?? "",
      objeto_contrato_origem: fd.objeto_contrato_origem ?? "",
      ressalva_exito: !!fd.ressalva_exito,
      substabelecer_e_devolver: !!fd.substabelecer_e_devolver,
    };
  }
  const o = fd.outorgante ?? {};
  return {
    data_documento: fd.data_documento ?? hoje,
    outorgante_pj: !o.nome || !!o.razao_social,
    outorgante_nome: o.razao_social ?? o.nome ?? "",
    outorgante_documento: o.cnpj ?? o.cpf ?? "",
    substabelecentes: fd.substabelecentes ?? [],
    substabelecidos: (fd.substabelecidos ?? []).map((s: Substabelecido) => ({
      nome: s.nome, genero: s.genero, estado_civil: s.estado_civil, oab: s.oab,
    })),
    endereco_substabelecidos: fd.endereco_substabelecidos ?? "",
    processos: fd.processos ?? [],
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

  if (tipo === "aditivo") {
    const a = estado as AditivoForm;
    obrig("data_contrato_origem", a.data_contrato_origem);
    obrig("objeto", a.objeto);
    if (!a.valor_mensal || a.valor_mensal <= 0) e["remuneracao.valor_mensal"] = "Informe o valor mensal";
    if (a.franquia_horas && !(parseInt(a.franquia_horas, 10) > 0)) e["remuneracao.franquia_horas"] = "Use um número inteiro maior que zero";
    if (a.valor_hora_excedente !== undefined && a.valor_hora_excedente <= 0) e["remuneracao.valor_hora_excedente"] = "Deve ser maior que zero";
    a.abrangencia.forEach((emp, i) => {
      obrig(`abrangencia.${i}.razao_social`, emp.razao_social);
      if (!cnpjOk(emp.cnpj)) e[`abrangencia.${i}.cnpj`] = "CNPJ inválido";
    });
  } else if (tipo === "distrato") {
    const d = estado as DistratoForm;
    obrig("data_contrato_origem", d.data_contrato_origem);
    obrig("objeto_contrato_origem", d.objeto_contrato_origem);
  } else {
    const s = estado as SubstabelecimentoForm;
    obrig("outorgante", s.outorgante_nome, "Informe o outorgante");
    if (!s.substabelecentes.length) e.substabelecentes = "Escolha ao menos um substabelecente";
    if (!s.substabelecidos.length) e.substabelecidos = "Informe ao menos um substabelecido";
    s.substabelecidos.forEach((x, i) => {
      obrig(`substabelecidos.${i}.nome`, x.nome);
      obrig(`substabelecidos.${i}.estado_civil`, x.estado_civil);
      obrig(`substabelecidos.${i}.oab`, x.oab);
    });
    obrig("endereco_substabelecidos", s.endereco_substabelecidos);
    if (!s.processos.length) e.processos = "Informe ao menos um processo";
    s.processos.forEach((p, i) => {
      if (!cnjValido(p.numero)) e[`processos.${i}.numero`] = "Número fora do padrão CNJ ou com dígito verificador errado";
    });
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

