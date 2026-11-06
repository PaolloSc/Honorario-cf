// Revisão por IA / Prévia desatualizadas (GLOSSARY.md):
//   node --experimental-strip-types src/app/lib/revisao.check.ts
import assert from "node:assert/strict";
import { chaveDaRevisao, situacaoDaRevisao } from "./revisao.ts";

const dados = { contratantes: [{ nome: "Ana" }], acessorios: { tem_reembolso: true }, envio: { socioEscritorio: "a@x" }, versao_formato: 2 };
const feita = { chave: chaveDaRevisao(dados) };

// nunca revisou (ex.: rascunho recém-retomado): não há o que comparar
assert.equal(situacaoDaRevisao(null, dados), "nenhuma");
// mesmos dados: em dia, nada é refeito (não gasta IA)
assert.equal(situacaoDaRevisao(feita, structuredClone(dados)), "em_dia");
// só o Envio mudou (e-mails, testemunhas, sócio): não muda o texto, não desatualiza
assert.equal(situacaoDaRevisao(feita, { ...dados, envio: { socioEscritorio: "b@x", testemunhaIds: [3] } }), "em_dia");
assert.equal(situacaoDaRevisao(feita, { ...dados, envio: undefined }), "em_dia");
// qualquer dado do contrato mudou depois da revisão
assert.equal(situacaoDaRevisao(feita, { ...dados, contratantes: [{ nome: "Ana Maria" }] }), "desatualizada");
assert.equal(situacaoDaRevisao(feita, { ...dados, acessorios: { tem_reembolso: false } }), "desatualizada");
assert.equal(situacaoDaRevisao(feita, { ...dados, ajustes_texto: { "2.2": { texto: "a", padrao: "b" } } }), "desatualizada");
// a chave não muda com a ordem em que o Envio foi gravado nem com leitura
const antes = JSON.stringify(dados);
chaveDaRevisao(dados);
assert.equal(JSON.stringify(dados), antes);

console.log("revisao.ts ok");
