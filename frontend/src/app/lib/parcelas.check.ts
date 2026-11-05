// node src/app/lib/parcelas.check.ts
import assert from "node:assert/strict";
import { diaDaData, dividirParcelas } from "./parcelas.ts";

assert.deepEqual(dividirParcelas(14000, 5), [2800, 2800, 2800, 2800, 2800]);
assert.deepEqual(dividirParcelas(10000, 3), [3333.33, 3333.33, 3333.34]);
for (const [t, n] of [[1234.56, 7], [0.1, 3], [99999.99, 12], [1, 1]] as const) {
  assert.equal(Math.round(dividirParcelas(t, n).reduce((a, b) => a + b, 0) * 100), Math.round(t * 100));
}
assert.deepEqual(dividirParcelas(100, 0), []);
assert.equal(diaDaData("2026-12-15"), 15);
assert.equal(diaDaData(""), undefined);
console.log("parcelas.ts ok");
