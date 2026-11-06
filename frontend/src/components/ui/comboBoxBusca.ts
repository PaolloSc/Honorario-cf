export type OpcaoCombo = { value: string; label: string };

export function semAcento(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "");
}

const norm = (s: string) => semAcento(s.trim().toLowerCase());

/** Opções cujo nome (ou qualquer palavra dele) começa pelo que foi digitado. */
export function filtrarOpcoes(opcoes: OpcaoCombo[], digitado: string): OpcaoCombo[] {
  const q = norm(digitado);
  return opcoes.filter((o) => {
    const l = norm(o.label);
    return l.startsWith(q) || l.includes(" " + q);
  });
}

/** Opção a confirmar quando a pessoa sai do campo sem clicar na lista: o nome digitado inteiro
 *  ou, se só uma opção bate com o que foi digitado, essa. Sem certeza, nada. */
export function opcaoParaConfirmar(opcoes: OpcaoCombo[], digitado: string): OpcaoCombo | undefined {
  if (!norm(digitado)) return undefined;
  const exata = opcoes.find((o) => norm(o.label) === norm(digitado));
  if (exata) return exata;
  const achadas = filtrarOpcoes(opcoes, digitado);
  return achadas.length === 1 ? achadas[0] : undefined;
}

/**
 * O que o ComboBox (sem texto livre) grava ao perder o foco; undefined = não mexe.
 * `digitou`: a pessoa mexeu no texto desde que focou (só focar e sair não esvazia o campo).
 */
export function valorAoSair(opcoes: OpcaoCombo[], digitado: string, valor: string, digitou: boolean): string | undefined {
  if (digitou && !norm(digitado)) return valor ? "" : undefined;
  const op = opcaoParaConfirmar(opcoes, digitado);
  return op && op.value !== valor ? op.value : undefined;
}
