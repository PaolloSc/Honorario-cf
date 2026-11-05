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

// Nenhum outro ponto da tela cria substabelecimento avulso: lista de contratos e a rota /documentos/novo.
const lista = readFileSync(new URL("../../app/contracts/page.tsx", import.meta.url), "utf8");
assert.ok(!/Novo substabelecimento/.test(lista) && !/tipo=substabelecimento/.test(lista), "atalho avulso na lista");
const novo = readFileSync(new URL("../../app/documentos/novo/page.tsx", import.meta.url), "utf8");
assert.ok(/tipo === "substabelecimento"\) \{/.test(novo) && !/tipo !== "substabelecimento"/.test(novo), "rota avulsa aberta");
console.log("sem substabelecimento avulso ok");
