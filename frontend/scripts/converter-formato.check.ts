// Teste com dados fictícios nos formatos antigos: node --experimental-strip-types scripts/converter-formato.check.ts
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";

const rodar = (entrada: unknown) =>
  JSON.parse(
    execFileSync(process.execPath, ["--experimental-strip-types", "--no-warnings", "scripts/converter-formato.ts"], {
      input: JSON.stringify(entrada),
    }).toString(),
  ) as Array<{ chave: string; dados: any }>;

const base = {
  contratantes: [{ tipo: "PF", nome: "Fulano Ficticio", cpf: "000", email: "f@x.test", endereco: "Rua X" }],
  escopos: [{ tipo: "consultivo", honorarios: [], pro_labore: { valor_total: 10, data_inicio: "2026-01-01", data_fim: "2026-06-30", duracao_meses: 6 } }],
  acessorios: { tem_reembolso: true, reembolso_limitado: false, tem_penalidade_inadimplemento: true },
  participacao: { tem_participacao: true, para_quem: ["Carla"], natureza: "indicacao", percentual_ou_valor: "5%" },
  contrato_origem_id: "abc", // campo de topo desconhecido pelo wizard: precisa sobreviver
};
const [a, b] = rodar([{ chave: "v1", dados: base }, { chave: "v2", dados: { contratantes: [], escopos: [], acessorios: {}, participacao: {} } }]);
assert.equal(a.dados.versao_formato, 2);
assert.equal(a.dados.acessorios.vigencia_inicio, "2026-01-01"); // vigência saiu do pró-labore
assert.equal(a.dados.escopos[0].pro_labore.data_inicio, undefined);
assert.equal(a.dados.participacao.participantes[0].nome, "Carla");
assert.equal(a.dados.contrato_origem_id, "abc");
assert.equal(b.dados.versao_formato, 2);
// rodar duas vezes dá o mesmo resultado
const [c] = rodar([{ chave: "v1", dados: a.dados }]);
assert.deepEqual(c.dados, a.dados);
console.log("converter-formato ok");
