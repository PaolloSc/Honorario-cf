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

console.log("validacaoHonorarios.ts ok");
