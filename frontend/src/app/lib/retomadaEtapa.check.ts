// Rascunho antigo parado na etapa N reabre na etapa N (dados 100% fictícios):
//   node --experimental-strip-types src/app/lib/retomadaEtapa.check.ts
import assert from "node:assert/strict";
import { normalizarFormData } from "./estadoWizard.ts";
import { primeiraEtapaInvalidaAntes, retomarRascunho, type Armazem } from "./rascunho.ts";
import { validateAcessorios, validateEscopos, validateParticipacao } from "./validacaoPassos.ts";
import { validateHonorarios } from "./validacaoHonorarios.ts";
import { validarContratantes } from "./validarContratantes.ts";

// as mesmas validações que o wizard aplica (ContractWizard.validateStep)
const validar = (etapa: number, d: any): string[] =>
  etapa === 1 ? validarContratantes(d, () => true)
  : etapa === 2 ? validateEscopos(d)
  : etapa === 3 ? validateHonorarios(d)
  : etapa === 4 ? validateAcessorios(d)
  : etapa === 5 ? validateParticipacao(d)
  : [];

// Rascunho no formato VELHO (sem versao_formato; participação com para_quem/natureza/percentual_ou_valor;
// vigência no pró-labore), parado na etapa 7.
const velho = {
  contratantes: [{ tipo: "PF", nome: "Fulana Ficticia", nacionalidade: "Brasileira", cpf: "529.982.247-25", profissao: "x", estado_civil: "Solteiro(a)", endereco: "Rua Ficticia, 1", email: "f@exemplo.test" }],
  incluir_partes_relacionadas: false,
  escopos: [{ tipo: "consultoria_lgpd", honorarios: ["pro_labore"], pro_labore: { valor_total: 100, tem_parcelamento: false, data_inicio: "2026-01-01", duracao_meses: 6 } }],
  acessorios: { tem_reembolso: true, reembolso_limitado: false, tem_penalidade_inadimplemento: true },
  participacao: { tem_participacao: true, responsavel_gestao: "Sócia Ficticia", para_quem: ["Sócia Ficticia"], natureza: "indicacao", percentual_ou_valor: "5%" },
};

const armazem = (dados: object, passo: number): Armazem => ({
  lerServidor: async () => ({ dados: dados as Record<string, unknown>, passo, atualizadoEm: 1, versao: "v" }),
  lerLocal: () => null,
  apagarServidor: async () => undefined,
  apagarLocal: () => undefined,
});

async function abrir(dados: object, passo: number) {
  const r = await retomarRascunho("r", armazem(dados, passo));
  assert.ok(r);
  const normal = normalizarFormData(r.dados as never);
  return { passo: r.passo, invalida: primeiraEtapaInvalidaAntes(r.passo, normal, validar) };
}

// formato velho, current_step 7 -> abre na 7, sem voltar a etapa nenhuma
{
  const a = await abrir(velho, 7);
  assert.equal(a.passo, 7);
  assert.equal(a.invalida, null);
}
// o mesmo rascunho parado em cada etapa abre nela
for (const passo of [1, 2, 3, 4, 5, 6, 7]) {
  const a = await abrir(velho, passo);
  assert.equal(a.passo, passo);
  assert.equal(a.invalida, null, `etapa ${passo}`);
}
// dado faltando atrás: a tela volta à primeira etapa inválida e diz o que falta (comportamento intencional)
{
  const semGestao = { ...velho, participacao: { ...velho.participacao, responsavel_gestao: "" } };
  const a = await abrir(semGestao, 7);
  assert.equal(a.invalida?.etapa, 5);
  assert.match(a.invalida!.erros[0], /responsável pela gestão/);
}
console.log("retomadaEtapa ok");
