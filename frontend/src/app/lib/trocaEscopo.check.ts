// node src/app/lib/trocaEscopo.check.ts
import assert from "node:assert/strict";
import { adicionarEscopo, removerEscopo } from "./trocaEscopo.ts";

const a: any = { tipo: "contencioso_judicial", honorarios: ["pro_labore"], pro_labore: { valor_total: 14000 } };
const novo = (tipo: string): any => ({ tipo, honorarios: [] });

// desmarca A e marca B: B herda o honorário
let r = removerEscopo([a], "contencioso_judicial", null);
assert.equal(r.escopos.length, 0);
assert.ok(r.guardado);
r = adicionarEscopo(r.escopos, novo("consultoria_contratual"), r.guardado);
assert.deepEqual(r.escopos[0].honorarios, ["pro_labore"]);
assert.equal(r.escopos[0].pro_labore.valor_total, 14000);
assert.equal(r.guardado, null);

// marca B antes e depois desmarca A: B (vazio) recebe
let s = adicionarEscopo([a], novo("consultoria_contratual"), null);
s = removerEscopo(s.escopos, "contencioso_judicial", s.guardado);
assert.equal(s.escopos.length, 1);
assert.equal(s.escopos[0].pro_labore.valor_total, 14000);

// escopo sem honorário não guarda nada; escopo com honorário ao lado não é sobrescrito
assert.equal(removerEscopo([novo("x") as any], "x" as any, null).guardado, null);
const b: any = { tipo: "b", honorarios: ["exito"], exito: { x: 1 } };
const t = removerEscopo([a, b], "contencioso_judicial", null);
assert.equal(t.escopos[0].exito.x, 1);
assert.ok(t.guardado);
console.log("trocaEscopo.ts ok");
