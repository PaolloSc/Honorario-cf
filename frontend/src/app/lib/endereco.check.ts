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

// buscarCep: único ponto que fala com o ViaCEP (fetch simulado, sem rede)
{
  const { buscarCep } = await import("./endereco.ts");
  const urls: string[] = [];
  const responder = (status: number, corpo: unknown) => {
    globalThis.fetch = (async (url: string) => {
      urls.push(url);
      return { ok: status === 200, status, json: async () => corpo };
    }) as never;
  };
  responder(200, { logradouro: "Rua A", bairro: "Centro", localidade: "Cidade Exemplo", uf: "MG" });
  assert.deepEqual(await buscarCep("30130-009"), { logradouro: "Rua A", bairro: "Centro", localidade: "Cidade Exemplo", uf: "MG" });
  assert.equal(urls.at(-1), "https://viacep.com.br/ws/30130009/json/");
  responder(200, { localidade: "Cidade Pequena", uf: "MG" }); // CEP único: sem rua nem bairro
  assert.deepEqual(await buscarCep("39999999"), { logradouro: "", bairro: "", localidade: "Cidade Pequena", uf: "MG" });
  responder(200, { erro: true });
  assert.equal(await buscarCep("00000000"), null);
  const antes = urls.length;
  assert.equal(await buscarCep("301"), null); // incompleto: nem consulta
  assert.equal(urls.length, antes);
  responder(500, {});
  await assert.rejects(buscarCep("30130009"));
}
