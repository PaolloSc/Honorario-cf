// "Cláusulas adicionais" seguem salvas como UM texto, uma cláusula por linha (formato do
// contrato e dos rascunhos já salvos); a tela edita como lista. O gerador numera cada linha
// não vazia na ordem em que aparecem.

/** Texto salvo -> itens da tela. Sempre devolve ao menos um campo (vazio). */
export function clausulasDoTexto(texto?: string | null): string[] {
  const itens = (texto ?? "").split(/\r?\n/).filter((l) => l.trim());
  return itens.length ? itens : [""];
}

/** Itens da tela -> texto salvo. Campo vazio é descartado; quebra de linha vira espaço
 *  (senão uma cláusula viraria duas). */
export function clausulasParaTexto(itens: string[]): string {
  return itens
    .map((c) => c.replace(/\s*[\r\n]+\s*/g, " ").trim())
    .filter(Boolean)
    .join("\n");
}
