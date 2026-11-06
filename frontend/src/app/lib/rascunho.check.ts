// Ciclo de vida do Rascunho com adapter em memória (sem API, sem localStorage):
//   node --experimental-strip-types src/app/lib/rascunho.check.ts
import assert from "node:assert/strict";
import { apagarRascunho, passoDeRetomada, retomarRascunho, type Armazem, type CopiaRascunho } from "./rascunho.ts";

function memoria(servidor: Record<string, CopiaRascunho>, local: Record<string, CopiaRascunho> = {}) {
  const chamadas: string[] = [];
  const arm: Armazem = {
    lerServidor: async (id) => {
      if (!servidor[id]) throw new Error("404");
      return servidor[id];
    },
    lerLocal: (id) => local[id] ?? null,
    apagarServidor: async (id) => void (chamadas.push(`servidor:${id}`), delete servidor[id]),
    apagarLocal: (id) => void (chamadas.push(`local:${id}`), delete local[id]),
  };
  return { arm, chamadas, servidor, local };
}
const copia = (passo: number, em: number, nome = "Ana", versao: string | null = "v1"): CopiaRascunho => ({
  dados: { contratantes: [{ nome }] }, passo, atualizadoEm: em, versao,
});

// retomada na etapa exata, inclusive a 7; fora da faixa é corrigida
assert.equal(passoDeRetomada(7), 7);
assert.equal(passoDeRetomada(6), 6);
assert.equal(passoDeRetomada(0), 1);
assert.equal(passoDeRetomada(99), 7);
assert.equal(passoDeRetomada(Number.NaN), 1);
{
  const { arm } = memoria({ r1: copia(7, 10) });
  const r = await retomarRascunho("r1", arm);
  assert.equal(r?.passo, 7);
  assert.equal(r?.versaoServidor, "v1");
  assert.deepEqual(r?.dados, { contratantes: [{ nome: "Ana" }] });
}
// a cópia local mais nova vence (o último salvamento no servidor falhou); a versão continua a do servidor
{
  const { arm } = memoria({ r1: copia(2, 10, "Servidor") }, { r1: copia(5, 20, "Local") });
  const r = await retomarRascunho("r1", arm);
  assert.equal((r?.dados.contratantes as { nome: string }[])[0].nome, "Local");
  assert.equal(r?.passo, 5);
  assert.equal(r?.versaoServidor, "v1");
}
// local mais velha: vale o servidor
{
  const { arm } = memoria({ r1: copia(2, 30, "Servidor") }, { r1: copia(5, 20, "Local") });
  assert.equal(((await retomarRascunho("r1", arm))?.dados.contratantes as { nome: string }[])[0].nome, "Servidor");
}
// servidor sem o rascunho: só a cópia local, sem versão; nenhuma cópia: null
{
  const { arm } = memoria({}, { r1: copia(3, 5) });
  const r = await retomarRascunho("r1", arm);
  assert.equal(r?.passo, 3);
  assert.equal(r?.versaoServidor, null);
  assert.equal(await retomarRascunho("outro", arm), null);
}

// apagar: servidor e cópia local, sempre juntos, e falha do servidor não impede apagar o local
{
  const m = memoria({ r1: copia(1, 1) }, { r1: copia(1, 1) });
  await apagarRascunho("r1", m.arm);
  assert.deepEqual(m.chamadas.sort(), ["local:r1", "servidor:r1"]);
  assert.equal(await retomarRascunho("r1", m.arm), null);
  const falha = memoria({}, { r2: copia(1, 1) });
  falha.arm.apagarServidor = async () => { throw new Error("rede"); };
  await apagarRascunho("r2", falha.arm); // não lança
  assert.equal(falha.local.r2, undefined);
}

console.log("rascunho.ts ok");
