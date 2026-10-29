// Verificação de documentos.ts (não há runner de testes no frontend):
//   node src/app/lib/documentos.check.ts
import assert from "node:assert/strict";
import { cnpjValido } from "./cnpj.ts";
import {
  agruparDerivados, valorEmReais, cnjValido, formatarCnj, ehDocumentoComplementar, errosDaApi, estadoDoFormData, estadoInicial,
  formatarOabNumero, lerOab, trocarUfOab, oabsDoTexto, oabTexto, oabsParaTexto, montarPayload, oabVazia, validar as validarBase, type AditivoForm, type SubstabelecimentoForm,
} from "./documentos.ts";

const validar = (t: any, e: any) => validarBase(t, e, cnpjValido);

// CNJ com dígito verificador (números fictícios com DV válido).
assert.ok(cnjValido("1234567-49.2020.8.13.0024"));
assert.ok(cnjValido("1111111-60.2023.4.06.0000"));
assert.ok(!cnjValido("1234567-50.2020.8.13.0024")); // DV errado
assert.ok(!cnjValido("123"));
assert.ok(cnjValido("12345674920208130024")); // sem máscara
assert.equal(formatarCnj("12345674920208130024"), "1234567-49.2020.8.13.0024");
assert.equal(formatarCnj("123"), "123");
assert.ok(!cnjValido(""));

assert.ok(ehDocumentoComplementar("distrato"));
assert.ok(!ehDocumentoComplementar("honorarios"));
assert.ok(!ehDocumentoComplementar(undefined));

// Aditivo: lista de alteracoes (alterar/excluir/adicionar); campos que nao cabem no tipo vao como null.
const alt = (tipo: "alterar" | "excluir" | "adicionar", clausula = "", texto = "") => ({ tipo, clausula, texto });
const ad = {
  ...(estadoInicial("aditivo", "2026-10-16") as AditivoForm),
  objeto: " auditoria ", data_contrato_origem: "2020-01-15",
  alteracoes: [alt("alterar", " Cláusula 3ª, item 3.2 ", " novo "), alt("excluir", "Cláusula 5ª", "sobra"), alt("adicionar", "sobra", "nova cláusula")],
};
assert.deepEqual(validar("aditivo", ad), {});
const p = montarPayload("aditivo", ad, "origem-1") as any;
assert.equal(p.objeto, "auditoria");
assert.equal(p.contrato_origem_id, "origem-1");
assert.equal(p.data_contrato_origem, "2020-01-15");
assert.deepEqual(p.alteracoes, [
  { tipo: "alterar", clausula: "Cláusula 3ª, item 3.2", texto: "novo" },
  { tipo: "excluir", clausula: "Cláusula 5ª", texto: null },
  { tipo: "adicionar", clausula: null, texto: "nova cláusula" },
]);
assert.equal(p.remuneracao, undefined);
assert.equal(p.abrangencia, undefined);
// Data do contrato original obrigatoria no aditivo (decisao do usuario).
assert.ok(validar("aditivo", { ...ad, data_contrato_origem: "" }).data_contrato_origem);
assert.ok(validar("aditivo", { ...ad, alteracoes: [] }).alteracoes);
assert.deepEqual(Object.keys(validar("aditivo", { ...ad, objeto: "", alteracoes: [alt("alterar"), alt("excluir"), alt("adicionar")] })).sort(),
  ["alteracoes.0.clausula", "alteracoes.0.texto", "alteracoes.1.clausula", "alteracoes.2.texto", "objeto"]);

// Distrato exige a data e o objeto do contrato original.
assert.deepEqual(Object.keys(validar("distrato", estadoInicial("distrato", "2026-10-16"))).sort(),
  ["data_contrato_origem", "objeto_contrato_origem"]);

// Distrato: só com "substabelecer e devolver" pede e envia os dados do substabelecimento.
const dis = { ...(estadoInicial("distrato", "2026-10-16") as any), data_contrato_origem: "2020-01-01", objeto_contrato_origem: "x" };
assert.deepEqual(validar("distrato", dis), {});
assert.equal((montarPayload("distrato", dis, "o") as any).substabelecimento, null);
// Pagamento: valor em reais no formato brasileiro; com valor exige a data; sem valor não envia nada.
assert.equal(valorEmReais("4.000,50"), 4000.5);
assert.equal(valorEmReais("R$ 4000"), 4000);
assert.equal(valorEmReais(""), null);
assert.equal(valorEmReais("abc"), null);
assert.deepEqual(Object.keys(validar("distrato", { ...dis, pagamento_valor: "4.000,00" })), ["pagamento_data"]);
assert.ok(validar("distrato", { ...dis, pagamento_valor: "0" }).pagamento_valor);
const pg = montarPayload("distrato", { ...dis, pagamento_valor: "4.000,00", pagamento_data: "2026-11-30" }, "o") as any;
assert.equal(pg.pagamento_valor, 4000);
assert.equal(pg.pagamento_data, "2026-11-30");
assert.equal((montarPayload("distrato", dis, "o") as any).pagamento_valor, null);
assert.equal((estadoDoFormData("distrato", pg, "h") as any).pagamento_valor, "4000");
const disSub = { ...dis, substabelecer_e_devolver: true };
for (const k of ["substabelecentes", "processos.0.numero", "substabelecidos.0.nome", "substabelecidos.0.oab"]) assert.ok(validar("distrato", disSub)[k], k);
const disOk = {
  ...disSub,
  substabelecentes: [{ nome: "Sócia", email: "s@cf.com", oab: { numero: "1", uf: "MG" } }],
  substabelecidos: [{ nome: "Novo", oab: { numero: "2", uf: "SP" } }],
  processos: [{ tipo: "Processo", numero: "1234567-49.2020.8.13.0024", descricao: "" }],
};
assert.deepEqual(validar("distrato", disOk), {});
const pd = montarPayload("distrato", disOk, "o") as any;
assert.equal(pd.substabelecimento.substabelecidos[0].oab, "OAB/SP sob o n.º 2");
assert.equal(pd.substabelecimento.substabelecentes[0].oab, "OAB/MG n.º 1");
// Distrato salvo antes da opção (sem dados do substabelecimento) abre normalmente.
assert.equal((estadoDoFormData("distrato", { substabelecer_e_devolver: true }, "h") as any).substabelecidos.length, 1);
assert.equal((estadoDoFormData("distrato", pd, "h") as any).substabelecidos[0].oab.uf, "SP");

// Substabelecimento sem origem: processo precisa de CNJ válido; listas vazias recusadas.
// Endereço e estado civil/gênero não são mais exigidos; OAB é só número + UF (padrão MG).
const sub = estadoInicial("substabelecimento", "2026-10-16") as SubstabelecimentoForm;
const erros = validar("substabelecimento", sub);
for (const k of ["outorgante", "substabelecentes", "processos.0.numero",
  "substabelecidos.0.nome", "substabelecidos.0.oab"]) assert.ok(erros[k], k);
assert.ok(!erros.endereco_substabelecidos && !erros["substabelecidos.0.estado_civil"]);
const ok: SubstabelecimentoForm = {
  ...sub, outorgante_nome: "OUTORGANTE LTDA", endereco_substabelecidos: "",
  substabelecentes: [{ nome: "Sócia", email: "s@cf.com", oab: { numero: "36.959", uf: "MG" } }],
  substabelecidos: [{ nome: "Beltrana", oab: { numero: "3.333", uf: "SP" } }],
  processos: [{ tipo: "", numero: "1234567-49.2020.8.13.0024", descricao: "A x B" }],
};
assert.deepEqual(validar("substabelecimento", ok), {});
assert.ok(validar("substabelecimento", { ...ok, substabelecentes: [{ nome: "S", email: "s", oab: { numero: "", uf: "MG" } }] })["substabelecentes.0.oab"]);
const ps = montarPayload("substabelecimento", ok, null) as any;
assert.equal(ps.contrato_origem_id, null);
assert.deepEqual(ps.outorgante, { razao_social: "OUTORGANTE LTDA", cnpj: null });
assert.equal(ps.processos[0].tipo, "Processo");
assert.equal(ps.substabelecentes[0].oab, "OAB/MG n.º 36.959");
assert.deepEqual(ps.substabelecidos, [{ nome: "Beltrana", oab: "OAB/SP sob o n.º 3.333" }]);
assert.equal(ps.endereco_substabelecidos, "");
assert.deepEqual((montarPayload("substabelecimento", { ...ok, outorgante_pj: false, outorgante_documento: "123" }, null) as any).outorgante,
  { nome: "OUTORGANTE LTDA", cpf: "123" });

// OAB: número formatado, UF padrão MG, leitura do texto salvo (formas antigas e novas).
assert.equal(formatarOabNumero("36959"), "36.959");
assert.equal(formatarOabNumero("1234567"), "1.234.567");
assert.deepEqual(oabVazia(), { numero: "", uf: "MG" });
assert.deepEqual(lerOab("OAB/MG nº 36.959"), { numero: "36.959", uf: "MG" });
assert.deepEqual(lerOab("OAB/SP sob o n.º 101.728"), { numero: "101.728", uf: "SP" });
assert.deepEqual(lerOab("123456"), { numero: "123.456", uf: "MG" });
// OAB fora do padrao nunca e' reescrita (achados da revisao): sufixo, outra UF, varias OABs, texto livre.
assert.deepEqual(lerOab("OAB/MG n.º 36.959-A"), { numero: "36.959-A", uf: "MG" });
assert.equal(oabTexto(lerOab("OAB/MG n.º 36.959-A")), "OAB/MG n.º 36.959-A");
assert.deepEqual(lerOab("OAB-SP 12345"), { numero: "12.345", uf: "SP" });
assert.deepEqual(lerOab("OAB/RJ sob o nº 1.234-b"), { numero: "1.234-B", uf: "RJ" });
const duas = "OAB/MG n.º 111.111 e OAB/SP n.º 222.222";
assert.equal(oabTexto(lerOab(duas)), duas);
assert.equal(oabTexto(lerOab(duas), true), duas);
const livre = "advogado inscrito na OAB 36.959 (MG)";
assert.equal(oabTexto(lerOab(livre)), livre);
assert.equal(oabTexto({ ...lerOab(duas), numero: "333" }), "OAB/MG n.º 333"); // editou: vale o que digitou
assert.deepEqual(lerOab(""), { numero: "", uf: "MG" });
// Trocar so a UF de um texto original limpa o numero (nao gera "OAB/SP n.º OABMGN11").
assert.deepEqual(trocarUfOab(lerOab(duas), "SP"), { numero: "", uf: "SP" });
assert.deepEqual(trocarUfOab({ numero: "36.959", uf: "MG" }, "SP"), { numero: "36.959", uf: "SP" });
assert.equal(formatarOabNumero("36959-a"), "36.959-A");

// OABs do cadastro de colaboradores: texto "numero/UF" (admin) <-> lista validada.
assert.deepEqual(oabsDoTexto("36.959/mg, 1234/SP"), [{ numero: "36959", uf: "MG" }, { numero: "1234", uf: "SP" }]);
assert.deepEqual(oabsDoTexto(""), []);
assert.equal(oabsDoTexto("12A/MG"), null);
assert.equal(oabsDoTexto("123/XX"), null);
assert.equal(oabsParaTexto([{ numero: "36959", uf: "MG" }]), "36959/MG");

// Ida e volta do form salvo (edição de rascunho), inclusive documento salvo com gênero/estado civil.
assert.deepEqual(estadoDoFormData("substabelecimento", ps, "h"), {
  ...ok, processos: [{ tipo: "Processo", numero: "1234567-49.2020.8.13.0024", descricao: "A x B" }],
  outorgante_documento: "",
});
const ad2 = estadoDoFormData("aditivo", p, "h") as AditivoForm;
assert.deepEqual(ad2.alteracoes[1], { tipo: "excluir", clausula: "Cláusula 5ª", texto: "" });
// Aditivo legado (remuneracao/abrangencia): abre, sem alteracoes herdadas.
assert.deepEqual((estadoDoFormData("aditivo", { objeto: "x", remuneracao: { valor_mensal: 1 }, abrangencia: [] }, "h") as AditivoForm).alteracoes, []);
const antigo = estadoDoFormData("substabelecimento", { ...ps, substabelecidos: [{ nome: "B", genero: "F", estado_civil: "casada", oab: "OAB/MG sob o nº 333.333" }] }, "h") as SubstabelecimentoForm;
assert.deepEqual(antigo.substabelecidos, [{ nome: "B", oab: { numero: "333.333", uf: "MG" } }]);

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
