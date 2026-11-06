// node --experimental-strip-types src/app/lib/endereco.check.ts
import assert from "node:assert/strict";
import { desmontarEndereco, formatCEP, montarEndereco } from "./endereco.ts";

const via = { logradouro: "Av. Afonso Pena", bairro: "Centro", localidade: "Belo Horizonte", uf: "MG" };

assert.equal(formatCEP("30130009"), "30130-009");
assert.equal(formatCEP("30130-009"), "30130-009");
assert.equal(formatCEP("301"), "301");

// ida e volta: o que a tela monta é o que a tela reabre
for (const [numero, complemento] of [["100", "sala 2"], ["100", ""], ["", "sala 2"], ["", ""]]) {
  const e = montarEndereco(via, numero, complemento, "30130009");
  assert.deepEqual(desmontarEndereco(e), { cep: "30130-009", numero, complemento }, e);
}
assert.equal(montarEndereco(via, "100", "", "30130009"), "Av. Afonso Pena, n. 100, Centro, Belo Horizonte/MG, CEP 30130-009");

// texto livre (CEP não achado, contrato antigo): nada a reidratar
assert.deepEqual(desmontarEndereco("Rua X, 10, Bairro"), { cep: "", numero: "", complemento: "" });
assert.deepEqual(desmontarEndereco(undefined), { cep: "", numero: "", complemento: "" });

console.log("endereco.ts ok");
