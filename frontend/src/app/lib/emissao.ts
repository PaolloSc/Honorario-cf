// Regras puras da tela de emissão de NFS-e (sem React nem rede), verificadas em emissao.check.ts.

export const STATUS_FATURA = ["rascunho", "aprovada", "emitindo", "emitida", "cancelada"] as const;
export type StatusFatura = (typeof STATUS_FATURA)[number];
export type StatusNota = "processando" | "autorizada" | "rejeitada" | "cancelada";

export const ROTULO_STATUS: Record<StatusFatura | StatusNota, string> = {
  rascunho: "Rascunho",
  aprovada: "Aprovada",
  emitindo: "Emitindo",
  emitida: "Emitida",
  cancelada: "Cancelada",
  processando: "Processando",
  autorizada: "Autorizada",
  rejeitada: "Rejeitada",
};

// Cores só por token do tema (nunca hex). O texto do selo diz a situação; a cor só reforça.
export const CLASSE_STATUS: Record<StatusFatura | StatusNota, string> = {
  rascunho: "bg-border/35 text-foreground",
  aprovada: "bg-primary/[0.16] text-primary-dark",
  emitindo: "bg-warning/[0.16] text-warning",
  emitida: "bg-success/[0.16] text-success",
  cancelada: "bg-border/35 text-muted",
  processando: "bg-warning/[0.16] text-warning",
  autorizada: "bg-success/[0.16] text-success",
  rejeitada: "bg-danger/[0.16] text-danger",
};

export function brl(valor: string | number | null | undefined): string {
  const n = Number(valor ?? 0);
  return (Number.isFinite(n) ? n : 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/** "2026-10" (input type=month) -> "2026-10-01" (competência é sempre o dia 1). */
export function competenciaDoMes(mes: string): string {
  return /^\d{4}-\d{2}$/.test(mes) ? `${mes}-01` : "";
}

/** "2026-10-01" -> "10/2026". */
export function rotuloCompetencia(iso: string): string {
  const m = /^(\d{4})-(\d{2})/.exec(iso);
  return m ? `${m[2]}/${m[1]}` : iso;
}

/** Só dígitos, para CPF, CNPJ, CEP e NBS digitados com máscara. */
/** Cadastro vindo da API sem os campos que só o servidor controla: o backend rejeita (422, extra=forbid) id/origem/ativo no corpo. */
export function semCamposDoServidor<T extends object>(t: T): Omit<T, "id" | "origem" | "ativo"> {
  const { id: _id, origem: _origem, ativo: _ativo, ...resto } = t as Record<string, unknown>;
  void _id; void _origem; void _ativo;
  return resto as Omit<T, "id" | "origem" | "ativo">;
}

export function digitos(v: string): string {
  return v.replace(/\D/g, "");
}

/** Mensagem legível de um erro da API ("409 {"detail":"..."}" ou 422 com lista). */
export function mensagemDeErro(e: unknown): string {
  const bruto = e instanceof Error ? e.message : String(e);
  const json = /\{[\s\S]*\}$/.exec(bruto);
  if (!json) return bruto;
  try {
    const d = JSON.parse(json[0]).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d.map((x) => `${Array.isArray(x.loc) ? x.loc.slice(1).join(".") : "campo"}: ${x.msg}`).join("; ");
    }
  } catch {
    /* mensagem não era JSON */
  }
  return bruto;
}

/** Erro de rede (sem resposta da API): as respostas da API chegam como "NNN corpo". Só neste caso
 *  repetir a mesma tentativa (mesma Idempotency-Key) é o caminho certo. */
export function ehErroDeRede(e: unknown): boolean {
  const msg = e instanceof Error ? e.message : String(e);
  return !/^\d{3}\b/.test(msg);
}

/** Texto do resultado de uma emissão, para o aviso depois do botão Emitir. */
export function resultadoDaEmissao(n: {
  status: string;
  numero_nfse: string | null;
  erro_codigo: string | null;
  erro_mensagem: string | null;
}): { tipo: "ok" | "erro" | "aviso"; texto: string } {
  if (n.status === "autorizada") {
    return { tipo: "ok", texto: `NFS-e autorizada${n.numero_nfse ? ` (nº ${n.numero_nfse})` : ""}.` };
  }
  if (n.status === "rejeitada") {
    return { tipo: "erro", texto: `Rejeitada${n.erro_codigo ? ` (${n.erro_codigo})` : ""}: ${n.erro_mensagem ?? ""}`.trim() };
  }
  return {
    tipo: "aviso",
    texto: "Sem resposta do SEFIN. Não emita de novo: abra Notas emitidas e use Consultar.",
  };
}

/** O que a fatura aceita fazer em cada status. */
export function acoesDaFatura(status: string): { aprovar: boolean; emitir: boolean; excluir: boolean; editar: boolean } {
  return {
    aprovar: status === "rascunho",
    editar: status === "rascunho",
    excluir: status === "rascunho",
    emitir: status === "aprovada",
  };
}

export const OPCOES_OP_SIMP_NAC = [
  { value: "1", label: "Não optante pelo Simples Nacional" },
  { value: "2", label: "MEI" },
  { value: "3", label: "Optante ME/EPP" },
];

export const OPCOES_REG_AP_TRIB_SN = [
  { value: "1", label: "1 – Tributos federais e municipal pelo Simples" },
  { value: "2", label: "2 – Federais pelo Simples, ISS fora do Simples" },
  { value: "3", label: "3 – Federais e ISS fora do Simples" },
];

export const OPCOES_REG_ESP_TRIB = [
  { value: "0", label: "0 – Nenhum" },
  { value: "1", label: "1 – Ato cooperado" },
  { value: "2", label: "2 – Estimativa" },
  { value: "3", label: "3 – Microempresa municipal" },
  { value: "4", label: "4 – Notário ou registrador" },
  { value: "5", label: "5 – Profissional autônomo" },
  { value: "6", label: "6 – Sociedade de profissionais" },
  { value: "9", label: "9 – Outros" },
];
