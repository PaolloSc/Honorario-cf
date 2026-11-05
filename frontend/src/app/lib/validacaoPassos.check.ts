// Verificação das etapas 2 a 5 (não há runner de testes no frontend):
//   node src/app/lib/validacaoPassos.check.ts
// Cada mensagem tem de dizer QUAL campo falta; os asteriscos das telas seguem estas regras.
import assert from "node:assert/strict";
import { validateEscopos, validateAcessorios, validateParticipacao } from "./validacaoPassos.ts";
import { validateHonorarios } from "./validacaoHonorarios.ts";

const dados = (extra: object) => ({ contratantes: [], escopos: [], participacao: {}, ...extra }) as never;
const esc = (extra: object) => ({ tipo: "contencioso_representacao", honorarios: [], ...extra });

// Etapa 2
assert.deepEqual(validateEscopos(dados({})), ["Selecione pelo menos um escopo."]);
assert.deepEqual(validateEscopos(dados({ escopos: [esc({ tipo: "outro" })] })), ["Escopo 1: descreva o escopo."]);
assert.deepEqual(validateEscopos(dados({ escopos: [esc({ tipo: "consultoria_elaboracao_documentos" })] })), ["Escopo 1: informe os documentos a elaborar."]);
assert.deepEqual(validateEscopos(dados({ escopos: [esc({ tipo: "consultoria_opiniao_legal" })] })), ["Escopo 1: informe a consulta ou tema do parecer."]);
assert.deepEqual(validateEscopos(dados({ escopos: [esc({})] })), []);

// Etapa 3
assert.deepEqual(validateHonorarios(dados({ escopos: [esc({})] })), ["Escopo 1: selecione pelo menos um tipo de honorário."]);
const h = (honorarios: string[], extra: object) => validateHonorarios(dados({ escopos: [esc({ honorarios, ...extra })] }));
assert.deepEqual(h(["hora_trabalhada"], { hora_trabalhada: { valor_hora: 0 } }), ["Escopo 1: informe o valor de hora trabalhada (maior que zero)."]);
assert.deepEqual(h(["pro_labore"], { pro_labore: { valor_total: 0 } }), ["Escopo 1: informe o valor de pró-labore (maior que zero)."]);
assert.deepEqual(h(["mensalidade"], { mensalidade: { valor: 0, subtipo: "advocacia_partido", dia_vencimento: "" } }), ["Escopo 1: informe o valor de mensalidade (maior que zero)."]);
assert.deepEqual(h(["permuta"], { permuta: { objeto_permuta: " " } }), ["Escopo 1: informe o objeto da permuta."]);
assert.deepEqual(h(["permuta"], { permuta: { objeto_permuta: "contabilidade" } }), []);
assert.deepEqual(h(["pro_labore"], { pro_labore: { valor_total: 1000, tipo_parcelamento: "mensal" } }), ["Escopo 1: pró-labore mensal precisa do número de parcelas.", "Escopo 1: pró-labore mensal precisa do vencimento da 1ª parcela."]);

// Etapa 4: nada obrigatório
assert.deepEqual(validateAcessorios(dados({})), []);

// Etapa 5
assert.deepEqual(validateParticipacao(dados({ participacao: { tem_participacao: false } })), ["Informe o responsável pela gestão do contrato."]);
assert.deepEqual(validateParticipacao(dados({ participacao: { responsavel_gestao: "Ana", tem_participacao: false } })), []);
assert.deepEqual(
  validateParticipacao(dados({ participacao: { responsavel_gestao: "Ana", tem_participacao: true, participantes: [{ nome: "Bia" }] } })),
  ["Informe o valor de Bia ou o critério geral da participação."],
);
console.log("validacaoPassos.check ok");
