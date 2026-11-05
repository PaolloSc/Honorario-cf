import type { EscopoItem } from "@/types/contract";

// Honorário não depende do escopo: trocar de escopo (desmarcar um e marcar outro) não pode apagá-lo.
// Os honorários moram dentro do escopo, então ao remover levamos o preenchimento para o escopo
// que ficou sem honorário (ou o guardamos para o próximo escopo marcado).
export type Honorarios = Pick<EscopoItem, "honorarios" | "hora_trabalhada" | "pro_labore" | "mensalidade" | "exito" | "permuta">;

export function honorariosDe(e: EscopoItem): Honorarios {
  const { honorarios, hora_trabalhada, pro_labore, mensalidade, exito, permuta } = e;
  return { honorarios, hora_trabalhada, pro_labore, mensalidade, exito, permuta };
}

const preenchido = (e: EscopoItem) => e.honorarios.length > 0;

/** Remove o escopo; o honorário dele vai para o primeiro escopo sem honorário, ou fica em `guardado`. */
export function removerEscopo(
  escopos: EscopoItem[],
  tipo: EscopoItem["tipo"],
  guardado: Honorarios | null,
): { escopos: EscopoItem[]; guardado: Honorarios | null } {
  const saindo = escopos.find((e) => e.tipo === tipo);
  const resto = escopos.filter((e) => e.tipo !== tipo);
  if (!saindo || !preenchido(saindo)) return { escopos: resto, guardado };
  const alvo = resto.findIndex((e) => !preenchido(e));
  if (alvo < 0) return { escopos: resto, guardado: honorariosDe(saindo) };
  return { escopos: resto.map((e, i) => (i === alvo ? { ...e, ...honorariosDe(saindo) } : e)), guardado: null };
}

/** Adiciona o escopo já com o honorário guardado (se houver). */
export function adicionarEscopo(
  escopos: EscopoItem[],
  novo: EscopoItem,
  guardado: Honorarios | null,
): { escopos: EscopoItem[]; guardado: Honorarios | null } {
  if (!guardado) return { escopos: [...escopos, novo], guardado };
  return { escopos: [...escopos, { ...novo, ...guardado }], guardado: null };
}
