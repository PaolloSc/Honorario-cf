// Verificação de cnpj.ts (não há runner de testes no frontend):
//   node src/app/lib/cnpj.check.ts
import assert from "node:assert/strict";
import { cnpjValido, formatarCNPJ, limparCNPJ } from "./cnpj.ts";

// Exemplo oficial da Receita (perguntas e respostas, pergunta 14): DV = 35.
assert.equal(cnpjValido("12.ABC.345/01DE-35"), true);
assert.equal(cnpjValido("12ABC34501DE35"), true);
assert.equal(cnpjValido("12abc34501de35"), true);
assert.equal(cnpjValido("12.ABC.345/01DE-36"), false);
// Numérico continua valendo (Banco do Brasil, resto < 2 → DV 0 no 1º dígito).
assert.equal(cnpjValido("00.000.000/0001-91"), true);
assert.equal(cnpjValido("00.000.000/0001-92"), false);
// DV com letra, tamanho errado e repetição não passam.
assert.equal(cnpjValido("12ABC34501DE3A"), false);
assert.equal(cnpjValido("12ABC34501DE3"), false);
assert.equal(cnpjValido("11111111111111"), false);

assert.equal(limparCNPJ("12.abc.345/01de-35xyz"), "12ABC34501DE35");
assert.equal(formatarCNPJ("12abc34501de35"), "12.ABC.345/01DE-35");
assert.equal(formatarCNPJ("12ABC"), "12.ABC");
assert.equal(formatarCNPJ("00000000000191"), "00.000.000/0001-91");

console.log("cnpj.ts ok");
