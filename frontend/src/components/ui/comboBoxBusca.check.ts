// Verificação de comboBoxBusca.ts: node src/components/ui/comboBoxBusca.check.ts
import assert from "node:assert/strict";
import { filtrarOpcoes, opcaoParaConfirmar } from "./comboBoxBusca.ts";

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
