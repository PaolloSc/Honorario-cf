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
assert.deepEqual(errosDoEscopo(escopo(pl({ tipo_parcelamento: "mensal" })), "E"), []);
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

console.log("validacaoHonorarios.ts ok");
