// Verificação do cliente HTTP único (não há runner de testes no frontend):
//   node src/app/lib/http.check.ts
import assert from "node:assert/strict";
import { API_BASE, chamarApi, chamarApiJson, ConflitoError, detalheDoErro, ErroApi, SessaoExpiradaError } from "./http.ts";

type Pedido = { url: string; init: RequestInit };
let pedidos: Pedido[] = [];
function fetchFalso(resposta: () => Response | Promise<Response>) {
  pedidos = [];
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    pedidos.push({ url, init });
    return resposta();
  }) as typeof fetch;
}
const headers = (i = 0) => pedidos[i].init.headers as Record<string, string>;

// base única + JSON
fetchFalso(() => new Response('{"ok":1}', { status: 200 }));
assert.deepEqual(await chamarApiJson("/api/x", { method: "POST", body: "{}" }), { ok: 1 });
assert.equal(pedidos[0].url, `${API_BASE}/api/x`);
assert.equal(headers()["Content-Type"], "application/json");

// FormData: sem Content-Type (o navegador põe o boundary); GET sem corpo também
fetchFalso(() => new Response("{}", { status: 200 }));
await chamarApiJson("/api/up", { method: "POST", body: new FormData() });
assert.equal(headers()["Content-Type"], undefined);
await chamarApiJson("/api/get");
assert.equal(headers(1)["Content-Type"], undefined);

// header de quem chama passa (Idempotency-Key)
await chamarApiJson("/api/emitir", { method: "POST", headers: { "Idempotency-Key": "k1" } });
assert.equal(headers(2)["Idempotency-Key"], "k1");

// 204 -> undefined
fetchFalso(() => new Response(null, { status: 204 }));
assert.equal(await chamarApiJson("/api/del", { method: "DELETE" }), undefined);

// erro: ErroApi com status e corpo; mensagem no formato único
fetchFalso(() => new Response('{"detail":"Aprove a fatura antes."}', { status: 422 }));
const e422 = await chamarApi("/api/f").catch((e) => e);
assert.ok(e422 instanceof ErroApi);
assert.equal(e422.status, 422);
assert.equal(e422.corpo, '{"detail":"Aprove a fatura antes."}');
assert.equal(e422.message, 'API error 422: {"detail":"Aprove a fatura antes."}');
assert.equal(detalheDoErro(e422), "Aprove a fatura antes.");
assert.equal(detalheDoErro(new Error("x")), null);

// 409 vira ConflitoError (que também é ErroApi)
fetchFalso(() => new Response('{"detail":{"codigo":"versao_desatualizada"}}', { status: 409 }));
const e409 = await chamarApi("/api/c").catch((e) => e);
assert.ok(e409 instanceof ConflitoError && e409 instanceof ErroApi);
assert.equal(JSON.parse(e409.corpo).detail.codigo, "versao_desatualizada");

// 401 sem sessão para renovar -> SessaoExpiradaError com o motivo
fetchFalso(() => new Response('{"detail":"Token expirado"}', { status: 401 }));
const e401 = await chamarApi("/api/me").catch((e) => e);
assert.ok(e401 instanceof SessaoExpiradaError);

// falha de rede -> Error "Falha ao conectar" (não é ErroApi)
fetchFalso(() => { throw new TypeError("Failed to fetch"); });
const rede = await chamarApi("/api/r").catch((e) => e);
assert.ok(!(rede instanceof ErroApi));
assert.match(rede.message, /^Falha ao conectar na API \(.*\): Failed to fetch$/);

// timeout próprio -> "Tempo esgotado"; abort de quem chama passa como AbortError
const pendurado = () => {
  const init = pedidos[pedidos.length - 1].init;
  return new Promise<Response>((_, rej) =>
    init.signal!.addEventListener("abort", () => rej(new DOMException("aborted", "AbortError"))));
};
fetchFalso(pendurado);
const tempo = await chamarApi("/api/lento", { timeoutMs: 10 }).catch((e) => e);
assert.match(tempo.message, /^Tempo esgotado ao conectar na API/);
const ctrl = new AbortController();
const p = chamarApi("/api/lento", { signal: ctrl.signal, timeoutMs: 10_000 }).catch((e) => e);
setTimeout(() => ctrl.abort(), 5);
assert.equal((await p).name, "AbortError");

console.log("http.check ok");
