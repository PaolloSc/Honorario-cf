// Verificação de comboBoxBusca.ts: node src/components/ui/comboBoxBusca.check.ts
import assert from "node:assert/strict";
import { filtrarOpcoes, opcaoParaConfirmar, valorAoSair } from "./comboBoxBusca.ts";

const socios = [
  { value: "g@x", label: "Gabriel Siqueira Eliazar de Carvalho" },
  { value: "ga@x", label: "Gabriela Souza" },
  { value: "m@x", label: "Mônica Furtado" },
];
assert.equal(filtrarOpcoes(socios, "monica").length, 1); // sem acento
assert.equal(filtrarOpcoes(socios, "furtado").length, 1); // sobrenome
assert.equal(filtrarOpcoes(socios, "gab").length, 2);
// Digitou o nome e saiu do campo sem clicar na lista:
assert.equal(opcaoParaConfirmar(socios, "Gabriel Siqueira Eliazar de Carvalho")?.value, "g@x");
assert.equal(opcaoParaConfirmar(socios, "gabriel siq")?.value, "g@x");
assert.equal(opcaoParaConfirmar(socios, "gabriel"), undefined); // Gabriela também começa assim
assert.equal(opcaoParaConfirmar(socios, "mon")?.value, "m@x");
assert.equal(opcaoParaConfirmar(socios, "gab"), undefined); // duas bateriam: não escolhe por ela
assert.equal(opcaoParaConfirmar(socios, "xyz"), undefined);
assert.equal(opcaoParaConfirmar(socios, "  "), undefined);
console.log("comboBoxBusca.ts ok");

// Ao sair do campo (issue #195): esvaziar de propósito limpa o valor; só focar e sair não mexe em nada.
assert.equal(valorAoSair(socios, "", "g@x", true), ""); // digitou e apagou tudo
assert.equal(valorAoSair(socios, "   ", "g@x", true), "");
assert.equal(valorAoSair(socios, "", "g@x", false), undefined); // só focou e saiu
assert.equal(valorAoSair(socios, "", "", true), undefined); // já estava vazio
assert.equal(valorAoSair(socios, "mon", "g@x", true), "m@x"); // confirma a opção inequívoca
assert.equal(valorAoSair(socios, "mon", "m@x", true), undefined); // já é ela
assert.equal(valorAoSair(socios, "gabriel", "g@x", true), undefined); // ambíguo: não decide
