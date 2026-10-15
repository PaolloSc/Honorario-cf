// Verificação de emissao.ts (não há runner de testes no frontend):
//   node src/app/lib/emissao.check.ts
import assert from "node:assert/strict";
import {
  acoesDaFatura, competenciaDoMes, digitos, mensagemDeErro, resultadoDaEmissao, rotuloCompetencia,
  CLASSE_STATUS, ROTULO_STATUS, STATUS_FATURA,
} from "./emissao.ts";

assert.equal(competenciaDoMes("2026-10"), "2026-10-01");
assert.equal(competenciaDoMes(""), "");
assert.equal(competenciaDoMes("10/2026"), "");
assert.equal(rotuloCompetencia("2026-10-01"), "10/2026");
assert.equal(digitos("30.130-001"), "30130001");
assert.equal(digitos("1.1301.90.00"), "113019000");

// erro da API: 409 com detail em texto, 422 com lista, texto puro
assert.equal(mensagemDeErro(new Error('409 {"detail":"Aprove a fatura antes."}')), "Aprove a fatura antes.");
assert.equal(
  mensagemDeErro(new Error('422 {"detail":[{"loc":["body","c_trib_nac"],"msg":"String should match pattern","type":"x"}]}')),
  "c_trib_nac: String should match pattern",
);
assert.equal(mensagemDeErro(new Error("Falha ao conectar")), "Falha ao conectar");

// resultado da emissão: autorizada, rejeitada e sem resposta (nunca sugere reenviar)
assert.deepEqual(resultadoDaEmissao({ status: "autorizada", numero_nfse: "752", erro_codigo: null, erro_mensagem: null }),
  { tipo: "ok", texto: "NFS-e autorizada (nº 752)." });
assert.equal(resultadoDaEmissao({ status: "rejeitada", numero_nfse: null, erro_codigo: "E0312", erro_mensagem: "não administrado" }).texto,
  "Rejeitada (E0312): não administrado");
const sem = resultadoDaEmissao({ status: "processando", numero_nfse: null, erro_codigo: null, erro_mensagem: null });
assert.equal(sem.tipo, "aviso");
assert.match(sem.texto, /Não emita de novo/);

// ações por status: só rascunho edita/exclui/aprova, só aprovada emite
assert.deepEqual(acoesDaFatura("rascunho"), { aprovar: true, editar: true, excluir: true, emitir: false });
assert.deepEqual(acoesDaFatura("aprovada"), { aprovar: false, editar: false, excluir: false, emitir: true });
for (const s of ["emitindo", "emitida", "cancelada"]) {
  assert.deepEqual(acoesDaFatura(s), { aprovar: false, editar: false, excluir: false, emitir: false }, s);
}

// todo status tem rótulo e classe (selo nunca só cor) e nenhuma cor é hex
for (const s of [...STATUS_FATURA, "processando", "autorizada", "rejeitada"] as const) {
  assert.ok(ROTULO_STATUS[s], s);
  assert.ok(CLASSE_STATUS[s] && !/#[0-9a-f]{3,6}/i.test(CLASSE_STATUS[s]), s);
}
console.log("emissao.check.ts ok");
