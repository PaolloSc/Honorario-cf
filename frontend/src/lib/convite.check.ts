// Verificação de convite.ts: node src/lib/convite.check.ts
import assert from "node:assert/strict";
import { entrarComConvite } from "./convite.ts";

const ok = { ok: true, error: null };
const csrf = { ok: true, error: "MissingCSRF" };
const seq = (...rs: Array<typeof ok | Error>) => {
  let n = 0;
  const f = async () => { const r = rs[Math.min(n++, rs.length - 1)]; if (r instanceof Error) throw r; return r; };
  return { f, chamadas: () => n };
};

let s = seq(ok);
assert.equal(await entrarComConvite(s.f), true);
assert.equal(s.chamadas(), 1);
s = seq(csrf, ok); // corrida do CSRF na 1ª visita: a 2ª tentativa entra
assert.equal(await entrarComConvite(s.f), true);
assert.equal(s.chamadas(), 2);
s = seq(new Error("rede"), ok);
assert.equal(await entrarComConvite(s.f), true);
s = seq(csrf); // link realmente inválido: desiste depois de 3
assert.equal(await entrarComConvite(s.f), false);
assert.equal(s.chamadas(), 3);
console.log("convite.ts ok");
