// Verificação do menu "Documentos deste contrato" (não há runner de testes no frontend):
//   node src/components/documentos/NovoDocumentoMenu.check.ts
// Não existe ação separada para o substabelecimento: ele sai junto com o distrato.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const fonte = readFileSync(new URL("./NovoDocumentoMenu.tsx", import.meta.url), "utf8");
assert.ok(!/Fazer substabelecimento/.test(fonte), "botão avulso de substabelecimento não deve existir");
assert.ok(!/url\("substabelecimento"\)/.test(fonte), "link para o formulário avulso não deve existir");
assert.ok(/url\("aditivo"\)/.test(fonte) && /url\("distrato"\)/.test(fonte), "aditivo e distrato continuam");
console.log("NovoDocumentoMenu ok");
