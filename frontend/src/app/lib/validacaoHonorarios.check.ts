// Verificação de validacaoHonorarios.ts (não há runner de testes no frontend):
//   node src/app/lib/validacaoHonorarios.check.ts
import assert from "node:assert/strict";
import { errosDoEscopo } from "./validacaoHonorarios.ts";

const pl = (extra: object) => ({ valor_total: 1000, tem_parcelamento: false, ...extra }) as never;
const escopo = (pro_labore: unknown) => ({ honorarios: ["pro_labore"], pro_labore }) as never;

// Customizado sem texto: bloqueia a etapa (antes caía em "parcela única").
assert.deepEqual(errosDoEscopo(escopo(pl({ tipo_parcelamento: "customizado" })), "Escopo 1"), [
  "Escopo 1: descreva o parcelamento customizado do pró-labore.",
]);
assert.equal(errosDoEscopo(escopo(pl({ tipo_parcelamento: "customizado", parcelamento_customizado: "  " })), "E").length, 1);
// Com texto, mensal ou parcela única: passa.
assert.deepEqual(errosDoEscopo(escopo(pl({ tipo_parcelamento: "customizado", parcelamento_customizado: "50/50" })), "E"), []);
assert.deepEqual(errosDoEscopo(escopo(pl({ tipo_parcelamento: "mensal", numero_parcelas: 2, valor_parcela: 500 })), "E"), []);
assert.deepEqual(errosDoEscopo(escopo(pl({})), "E"), []);
// Pró-labore desmarcado não valida dado que ficou para trás.
assert.deepEqual(
  errosDoEscopo({ honorarios: [], pro_labore: pl({ tipo_parcelamento: "customizado" }) } as never, "E"),
  [],
);

// Desconto percentual acima de 100% bloqueia a etapa (achado da revisão da #110).
const comDesconto = (pct: number, tipo = "percentual") =>
  ({ honorarios: ["mensalidade"], mensalidade: { tem_desconto: true, desconto_tipo: tipo, desconto_percentual: pct } }) as never;
assert.deepEqual(errosDoEscopo(comDesconto(150), "Escopo 2"), [
  "Escopo 2: o desconto de mensalidade não pode passar de 100%.",
]);
assert.deepEqual(errosDoEscopo(comDesconto(100), "E"), []);
assert.deepEqual(errosDoEscopo(comDesconto(150, "livre"), "E"), []);
assert.deepEqual(
  errosDoEscopo({ honorarios: [], mensalidade: { tem_desconto: true, desconto_percentual: 150 } } as never, "E"),
  [],
);

// Êxito de 0 a 100 e valores maiores que zero (achados 4 e 10 da varredura).
const exito = (percentual: number) => ({ honorarios: ["exito"], exito: { percentual } }) as never;
assert.deepEqual(errosDoEscopo(exito(150), "E1"), ["E1: o percentual de êxito deve ficar entre 0 e 100."]);
assert.equal(errosDoEscopo(exito(-5), "E").length, 1);
assert.deepEqual(errosDoEscopo(exito(100), "E"), []);
assert.deepEqual(errosDoEscopo(exito(0), "E"), []);
const hora = (valor_hora: number) => ({ honorarios: ["hora_trabalhada"], hora_trabalhada: { valor_hora } }) as never;
assert.deepEqual(errosDoEscopo(hora(0), "E1"), ["E1: informe o valor de hora trabalhada (maior que zero)."]);
assert.equal(errosDoEscopo(hora(-1), "E").length, 1);
assert.deepEqual(errosDoEscopo(hora(300), "E"), []);
assert.equal(errosDoEscopo({ honorarios: ["mensalidade"], mensalidade: { valor: 0 } } as never, "E").length, 1);
assert.deepEqual(
  errosDoEscopo({ honorarios: ["mensalidade"], mensalidade: { valor: 0, faixas_preco: [{ faixa: "a", valor: "1" }] } } as never, "E"),
  [],
);
assert.equal(errosDoEscopo(escopo(pl({ valor_total: -500 })), "E").length, 1);
assert.deepEqual(
  errosDoEscopo(escopo(pl({ valor_total: 0, tipo_parcelamento: "customizado", parcelamento_customizado: "a combinar" })), "E"),
  [],
);
assert.deepEqual(errosDoEscopo({ honorarios: [], hora_trabalhada: { valor_hora: 0 } } as never, "E"), []);

// Pró-labore mensal, permuta e êxito "Outro" (achados 11 e 12 da varredura).
const mensal = (extra: object) => escopo(pl({ tipo_parcelamento: "mensal", valor_total: 12000, ...extra }));
assert.equal(errosDoEscopo(mensal({}), "E").length, 1); // sem nº nem valor da parcela
assert.equal(errosDoEscopo(mensal({ numero_parcelas: 3, valor_parcela: 1000 }), "E").length, 1); // 3000 != 12000
assert.deepEqual(errosDoEscopo(mensal({ numero_parcelas: 3, valor_parcela: 4000 }), "E"), []);
assert.deepEqual(errosDoEscopo(mensal({ valor_total: 10000, numero_parcelas: 3, valor_parcela: 3333.33 }), "E"), []);
assert.equal(errosDoEscopo({ honorarios: ["permuta"], permuta: { objeto_permuta: " " } } as never, "E").length, 1);
assert.deepEqual(errosDoEscopo({ honorarios: ["permuta"], permuta: { objeto_permuta: "imóvel" } } as never, "E"), []);
assert.equal(errosDoEscopo({ honorarios: ["exito"], exito: { forma_pagamento: "a definir" } } as never, "E").length, 1);
assert.deepEqual(errosDoEscopo({ honorarios: ["exito"], exito: { forma_pagamento: "em 2 vezes" } } as never, "E"), []);

// Êxito variável precisa de faixa completa (item 7).
const variavel = (faixas: object[]) =>
  ({ honorarios: ["exito"], exito: { subtipo: "percentual_variavel", faixas_percentual: faixas } }) as never;
assert.equal(errosDoEscopo(variavel([]), "E").length, 1);
assert.equal(errosDoEscopo(variavel([{ faixa: "até 100 mil", percentual: "" }]), "E").length, 1);
assert.deepEqual(errosDoEscopo(variavel([{ faixa: "até 100 mil", percentual: "10" }]), "E"), []);
assert.equal(errosDoEscopo(variavel([{ faixa: "a", percentual: "a combinar" }]), "E").length, 1);
assert.equal(errosDoEscopo(variavel([{ faixa: "a", percentual: "300" }]), "E").length, 1);
assert.equal(errosDoEscopo(variavel([{ faixa: "a", percentual: "10" }, { faixa: "b", percentual: "" }]), "E").length, 1);
assert.deepEqual(errosDoEscopo(variavel([{ faixa: "a", percentual: "10,5%" }, { faixa: "", percentual: "" }]), "E"), []);
// Período invertido (revisão da Angela).
assert.equal(errosDoEscopo({ honorarios: ["mensalidade"], mensalidade: { data_inicio: "2026-12-31", data_fim: "2026-01-10" } } as never, "E").length, 1);

console.log("validacaoHonorarios.ts ok");
