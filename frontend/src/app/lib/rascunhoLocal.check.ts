// Verificação de rascunhoLocal.ts (não há runner de testes no frontend):
//   node src/app/lib/rascunhoLocal.check.ts
import assert from "node:assert/strict";

const mem = new Map<string, string>();
(globalThis as Record<string, unknown>).localStorage = {
  get length() { return mem.size; },
  key: (i: number) => [...mem.keys()][i] ?? null,
  getItem: (k: string) => mem.get(k) ?? null,
  setItem: (k: string, v: string) => void mem.set(k, v),
  removeItem: (k: string) => void mem.delete(k),
};
const { gravarLocal, lerLocal, listarLocais, limparLocais } = await import("./rascunhoLocal.ts");

const form = { contratantes: [{ nome: "Cliente X" }] };
gravarLocal("rasc-a-0001", form, 3, "a@cf.adv.br");
// dono lê; outra pessoa no mesmo navegador não vê nem abre
assert.equal(lerLocal("rasc-a-0001", "a@cf.adv.br")?.client_name, "Cliente X");
assert.equal(lerLocal("rasc-a-0001", "b@cf.adv.br"), null);
assert.equal(listarLocais("b@cf.adv.br").length, 0);
assert.equal(listarLocais("a@cf.adv.br").length, 1);
// sem dono (sessão carregando) não grava nem lê
gravarLocal("rasc-x-0001", form, 1, "");
assert.equal(mem.has("cf:rascunho:rasc-x-0001"), false);
assert.equal(lerLocal("rasc-a-0001", ""), null);
// cópia antiga sem owner_email fica invisível
mem.set("cf:rascunho:rasc-old-001", JSON.stringify({ draft_id: "rasc-old-001", form_data: form, current_step: 1, client_name: "", updated_at: new Date().toISOString() }));
assert.equal(lerLocal("rasc-old-001", "a@cf.adv.br"), null);
// mais de 7 dias: some ao ser lida
const velho = JSON.parse(mem.get("cf:rascunho:rasc-a-0001")!);
velho.updated_at = new Date(Date.now() - 8 * 86400000).toISOString();
mem.set("cf:rascunho:rasc-a-0001", JSON.stringify(velho));
assert.equal(lerLocal("rasc-a-0001", "a@cf.adv.br"), null);
assert.equal(mem.has("cf:rascunho:rasc-a-0001"), false);
// Sair limpa tudo do prefixo, e só ele
mem.set("outra-chave", "1");
gravarLocal("rasc-b-0001", form, 2, "b@cf.adv.br");
limparLocais();
assert.deepEqual([...mem.keys()], ["outra-chave"]);
console.log("rascunhoLocal.check ok");
