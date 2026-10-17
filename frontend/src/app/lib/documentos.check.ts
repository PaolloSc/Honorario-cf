// Verificação de documentos.ts (não há runner de testes no frontend):
//   node src/app/lib/documentos.check.ts
import assert from "node:assert/strict";
import { cnpjValido } from "./cnpj.ts";
import {
  agruparDerivados, cnjValido, ehDocumentoComplementar, errosDaApi, estadoDoFormData, estadoInicial,
  montarPayload, validar as validarBase, type AditivoForm, type SubstabelecimentoForm,
} from "./documentos.ts";

const validar = (t: any, e: any) => validarBase(t, e, cnpjValido);

// CNJ com dígito verificador (números fictícios com DV válido).
assert.ok(cnjValido("1234567-49.2020.8.13.0024"));
assert.ok(cnjValido("1111111-60.2023.4.06.0000"));
assert.ok(!cnjValido("1234567-50.2020.8.13.0024")); // DV errado
assert.ok(!cnjValido("123"));
assert.ok(!cnjValido(""));

assert.ok(ehDocumentoComplementar("distrato"));
assert.ok(!ehDocumentoComplementar("honorarios"));
assert.ok(!ehDocumentoComplementar(undefined));

// Aditivo: franquia e hora excedente opcionais; vazio vira null (o backend omite a cláusula).
const ad = { ...(estadoInicial("aditivo", "2026-10-16") as AditivoForm), objeto: " auditoria ", valor_mensal: 1500, data_contrato_origem: "2020-01-15" };
assert.deepEqual(validar("aditivo", ad), {});
const p = montarPayload("aditivo", ad, "origem-1") as any;
assert.equal(p.objeto, "auditoria");
assert.equal(p.contrato_origem_id, "origem-1");
assert.equal(p.remuneracao.franquia_horas, null);
assert.equal(p.remuneracao.valor_hora_excedente, null);
assert.equal(p.data_contrato_origem, "2020-01-15");
// Data do contrato original obrigatoria no aditivo (decisao do usuario).
assert.ok(validar("aditivo", { ...ad, data_contrato_origem: "" }).data_contrato_origem);
assert.equal(montarPayload("aditivo", { ...ad, franquia_horas: "5" }, "o").remuneracao.franquia_horas, 5);
assert.deepEqual(Object.keys(validar("aditivo", { ...ad, valor_mensal: undefined, objeto: "" })).sort(), ["objeto", "remuneracao.valor_mensal"]);
assert.ok(validar("aditivo", { ...ad, abrangencia: [{ razao_social: "X", cnpj: "11" }] })["abrangencia.0.cnpj"]);

// Distrato exige a data e o objeto do contrato original.
assert.deepEqual(Object.keys(validar("distrato", estadoInicial("distrato", "2026-10-16"))).sort(),
  ["data_contrato_origem", "objeto_contrato_origem"]);

// Substabelecimento sem origem: processo precisa de CNJ válido; listas vazias recusadas.
const sub = estadoInicial("substabelecimento", "2026-10-16") as SubstabelecimentoForm;
const erros = validar("substabelecimento", sub);
for (const k of ["outorgante", "substabelecentes", "endereco_substabelecidos", "processos.0.numero",
  "substabelecidos.0.nome", "substabelecidos.0.oab", "substabelecidos.0.estado_civil"]) assert.ok(erros[k], k);
const ok: SubstabelecimentoForm = {
  ...sub, outorgante_nome: "OUTORGANTE LTDA", endereco_substabelecidos: "Rua A, 1",
  substabelecentes: [{ nome: "Sócia", email: "s@cf.com", oab: "OAB/MG nº 1" }],
  substabelecidos: [{ nome: "Beltrana", genero: "F", estado_civil: "casada", oab: "OAB/MG sob o nº 3" }],
  processos: [{ tipo: "", numero: "1234567-49.2020.8.13.0024", descricao: "A x B" }],
};
assert.deepEqual(validar("substabelecimento", ok), {});
const ps = montarPayload("substabelecimento", ok, null) as any;
assert.equal(ps.contrato_origem_id, null);
assert.deepEqual(ps.outorgante, { razao_social: "OUTORGANTE LTDA", cnpj: null });
assert.equal(ps.processos[0].tipo, "Processo");
assert.deepEqual((montarPayload("substabelecimento", { ...ok, outorgante_pj: false, outorgante_documento: "123" }, null) as any).outorgante,
  { nome: "OUTORGANTE LTDA", cpf: "123" });

// Ida e volta do form salvo (edição de rascunho).
assert.deepEqual(estadoDoFormData("substabelecimento", ps, "h"), {
  ...ok, processos: [{ tipo: "Processo", numero: "1234567-49.2020.8.13.0024", descricao: "A x B" }],
  outorgante_documento: "",
});
const ad2 = estadoDoFormData("aditivo", { ...p, remuneracao: { valor_mensal: 1500, franquia_horas: 2 } }, "h") as AditivoForm;
assert.equal(ad2.franquia_horas, "2");
assert.equal(ad2.valor_mensal, 1500);

// Erros 422 do backend em português, por campo.
const r = errosDaApi(new Error('API error 422: {"detail":[{"loc":["processos",0,"numero"],"msg":"Value error, Número de processo inválido","type":"value_error"},'
  + '{"loc":["remuneracao","valor_mensal"],"msg":"Input should be greater than 0","type":"greater_than"},'
  + '{"loc":["objeto"],"msg":"Field required","type":"missing"}]}'));
assert.equal(r.campos["processos.0.numero"], "Número de processo inválido");
assert.equal(r.campos["remuneracao.valor_mensal"], "Deve ser maior que zero");
assert.equal(r.campos["objeto"], "Campo obrigatório");
assert.equal(errosDaApi(new Error('API error 409: {"detail":"Já existe um distrato para este contrato"}')).geral, "Já existe um distrato para este contrato");
assert.equal(errosDaApi(new Error("Falha ao conectar")).geral, "Falha ao conectar");

// Lista: derivados logo abaixo do pai; órfãos (pai em outra página) ficam soltos.
const itens = [
  { contract_id: "d1", contrato_origem_id: "p1" },
  { contract_id: "x" },
  { contract_id: "p1" },
  { contract_id: "d2", contrato_origem_id: "p1" },
  { contract_id: "o", contrato_origem_id: "fora" },
];
assert.deepEqual(agruparDerivados(itens).map((g) => `${g.derivado ? ">" : ""}${g.item.contract_id}`),
  ["x", "p1", ">d1", ">d2", "o"]);

console.log("documentos.ts ok");
