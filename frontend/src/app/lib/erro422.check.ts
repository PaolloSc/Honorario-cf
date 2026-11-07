// Verificação de erro422.ts: node src/app/lib/erro422.check.ts
import assert from "node:assert/strict";
import { ehErro422, errosPorCampo, mensagemDo422, textoDoErro } from "./erro422.ts";

const corpo = (detail: unknown) => JSON.stringify({ detail });
assert.equal(
  mensagemDo422(corpo([{ type: "value_error", msg: "Value error, Escopo 1: o percentual de êxito deve ficar entre 0 e 100." }])),
  "Escopo 1: o percentual de êxito deve ficar entre 0 e 100.",
);
assert.equal(mensagemDo422(corpo([{ msg: "A" }, { msg: "Value error, B" }])), "A B");
assert.equal(mensagemDo422(corpo("texto")), "texto");
assert.equal(mensagemDo422("nao json"), null);
assert.equal(mensagemDo422(corpo([])), null);
// errosDaApi (documentos complementares) lê a mensagem crua "API error 422: {...}": o api.ts não a altera.
const cru = new Error('API error 422: {"detail":[{"loc":["body","x"],"msg":"Value error, Falta algo."}]}');
assert.equal(textoDoErro(cru), "Falta algo.");
assert.equal(ehErro422(cru), true);
assert.equal(ehErro422(new Error("Falha ao conectar")), false);
assert.equal(textoDoErro(new Error("Falha ao conectar")), "Falha ao conectar");
assert.equal(textoDoErro("x"), "Erro desconhecido");
// errosPorCampo: loc do backend vira o caminho do campo
const e422 = (detail: unknown) => new Error(`API error 422: ${JSON.stringify({ detail })}`);
assert.deepEqual(
  errosPorCampo(e422([
    { loc: ["body", "escopos", 0, "pro_labore", "numero_parcelas"], msg: "Escopo 1: falta o número." },
    { loc: ["body", "escopos", 0, "pro_labore", "numero_parcelas"], msg: "segunda, ignorada" },
    { loc: ["body"], msg: "Value error, sem campo" },
    { loc: ["body", "form_data", "escopos", 1, "pro_labore", "adicionais", 0, "valor_parcela"], msg: "Value error, X" },
  ])),
  { "escopos.0.pro_labore.numero_parcelas": "Escopo 1: falta o número.", "escopos.1.pro_labore.adicionais.0.valor_parcela": "X" },
);
assert.deepEqual(errosPorCampo(new Error("API error 500: x")), {});
assert.deepEqual(errosPorCampo(new Error("API error 422: nao json")), {});
assert.deepEqual(errosPorCampo("x"), {});
console.log("erro422.ts ok");
