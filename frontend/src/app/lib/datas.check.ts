// Verificação de datas.ts (não há runner de testes no frontend):
//   node src/app/lib/datas.check.ts
import assert from "node:assert/strict";
import { dataDaApi, formatarData, formatarDataHora } from "./datas.ts";

// Timestamp da API sem fuso é UTC: 18:23 UTC = 15:23 em Brasília.
assert.equal(formatarDataHora("2026-09-23T18:23:16"), "23/09/2026, 15:23");
// Com fuso explícito, respeita o fuso.
assert.equal(formatarDataHora("2026-09-23T18:23:16+00:00"), "23/09/2026, 15:23");
assert.equal(formatarDataHora("2026-09-23T18:23:16Z"), "23/09/2026, 15:23");
// 01:00 UTC ainda é o dia anterior em Brasília.
assert.equal(formatarData("2026-09-24T01:00:00"), "23/09/2026");
// Só a data não muda de dia.
assert.equal(formatarData("2026-09-23"), "23/09/2026");
assert.equal(dataDaApi("2026-09-23T18:23:16").toISOString(), "2026-09-23T18:23:16.000Z");

console.log("datas.ts ok");
