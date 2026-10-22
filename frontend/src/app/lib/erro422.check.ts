// Verificação de erro422.ts: node src/app/lib/erro422.check.ts
import assert from "node:assert/strict";
import { mensagemDo422 } from "./erro422.ts";

const corpo = (detail: unknown) => JSON.stringify({ detail });
assert.equal(
  mensagemDo422(corpo([{ type: "value_error", msg: "Value error, Escopo 1: o percentual de êxito deve ficar entre 0 e 100." }])),
  "Escopo 1: o percentual de êxito deve ficar entre 0 e 100.",
);
assert.equal(mensagemDo422(corpo([{ msg: "A" }, { msg: "Value error, B" }])), "A B");
assert.equal(mensagemDo422(corpo("texto")), "texto");
assert.equal(mensagemDo422("nao json"), null);
assert.equal(mensagemDo422(corpo([])), null);
console.log("erro422.ts ok");
