// Verificação de clausulasAdicionais.ts (não há runner de testes no frontend):
//   node src/app/lib/clausulasAdicionais.check.ts
import assert from "node:assert/strict";
import { clausulasDoTexto, clausulasParaTexto } from "./clausulasAdicionais.ts";

// Sem nada salvo: um campo vazio sozinho.
assert.deepEqual(clausulasDoTexto(undefined), [""]);
assert.deepEqual(clausulasDoTexto(""), [""]);
assert.deepEqual(clausulasDoTexto("  \n\n"), [""]);
// Contrato antigo (uma cláusula) aparece como a primeira.
assert.deepEqual(clausulasDoTexto("Cláusula antiga."), ["Cláusula antiga."]);
// Várias linhas viram vários campos, na ordem; linhas vazias somem (CRLF também).
assert.deepEqual(clausulasDoTexto("A\r\n\r\nB\nC"), ["A", "B", "C"]);

// Ida e volta preserva ordem; campo vazio é ignorado.
assert.equal(clausulasParaTexto(["A", "", "  ", "B"]), "A\nB");
assert.equal(clausulasParaTexto([""]), "");
// Cláusula com quebra de linha colada não vira duas.
assert.equal(clausulasParaTexto(["linha 1\nlinha 2", "B"]), "linha 1 linha 2\nB");
assert.equal(clausulasParaTexto(clausulasDoTexto("A\nB")), "A\nB");
console.log("clausulasAdicionais ok");
