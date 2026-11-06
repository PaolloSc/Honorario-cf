// Estado do wizard (Envio e Ficha interna). Não há runner de testes no frontend:
//   node --experimental-strip-types src/app/lib/estadoWizard.check.ts
// Cruza o mesmo seam que as etapas usam: abrir -> alterar -> ler.
import assert from "node:assert/strict";
import {
  DADOS_INICIAIS,
  alterarEnvio,
  destinatarios,
  montarFicha,
  normalizarFormData,
  nomeDoContratante,
  socioDoEnvio,
  sugerirSocio,
  temFichaParaFinanceiro,
  VERSAO_FORMATO,
} from "./estadoWizard.ts";

const pf = (nome: string, email = "") => ({ tipo: "PF", nome, email }) as never;
const pj = (razao_social: string, email = "") => ({ tipo: "PJ", razao_social, email }) as never;
const dados = (extra: object = {}) =>
  normalizarFormData({ contratantes: [pf("Ana", "ana@x.com"), pj("Beta Ltda", "beta@x.com")], ...extra } as never);

const colabs = [
  { name: "Carla Sócia", email: "carla@cf.com", role: "socio" },
  { name: "Davi Sócio", email: "davi@cf.com", role: "socio" },
  { name: "Eva Associada", email: "eva@cf.com", role: "associado" },
];

// ── destinatários: derivados dos contratantes; o salvo vale se os contratantes são os mesmos ──
assert.deepEqual(destinatarios(dados()), [
  { email: "ana@x.com", nome: "Ana" },
  { email: "beta@x.com", nome: "Beta Ltda" },
]);
const editado = alterarEnvio(dados(), { recipients: [{ email: "novo@x.com", nome: "Ana" }, { email: "beta@x.com", nome: "Beta Ltda" }] });
assert.equal(destinatarios(editado)[0].email, "novo@x.com");
// contratante a mais: o salvo não serve mais (ordem/quantidade mudou), volta ao cadastro
const maisUm = normalizarFormData({ ...editado, contratantes: [...editado.contratantes, pf("Cris", "cris@x.com")] } as never);
assert.deepEqual(destinatarios(maisUm).map((r) => r.email), ["ana@x.com", "beta@x.com", "cris@x.com"]);
assert.equal(nomeDoContratante(pj("Beta Ltda")), "Beta Ltda");

// ── sócio que assina: escolhido > sugerido > vazio; "esvaziado" difere de "não escolhido" ──
const base = dados({ participacao: { tem_participacao: false, responsavel_gestao: "Davi Sócio" } });
assert.equal(sugerirSocio(base, colabs), "davi@cf.com");
assert.equal(socioDoEnvio(base, colabs), "davi@cf.com"); // sem tocar no campo, a sugestão vale
assert.equal(socioDoEnvio(alterarEnvio(base, { socioEscritorio: "carla@cf.com" }), colabs), "carla@cf.com");
assert.equal(socioDoEnvio(alterarEnvio(base, { socioEscritorio: "" }), colabs), ""); // esvaziou de propósito
// gestão que não é sócio: cai no primeiro participante que é sócio
const porParticipante = dados({
  participacao: { tem_participacao: true, responsavel_gestao: "Eva Associada", participantes: [{ nome: "Carla Sócia", natureza: "x" }] },
});
assert.equal(sugerirSocio(porParticipante, colabs), "carla@cf.com");
// um único sócio cadastrado: não há o que escolher
assert.equal(sugerirSocio(dados(), [colabs[0], colabs[2]]), "carla@cf.com");
assert.equal(sugerirSocio(dados(), colabs), undefined); // dois sócios, ninguém indicado
assert.equal(socioDoEnvio(dados(), []), ""); // colaboradores ainda não carregaram

// ── ler e sugerir nunca alteram os dados ──
const antes = JSON.stringify(base);
destinatarios(base);
socioDoEnvio(base, colabs);
assert.equal(JSON.stringify(base), antes);
assert.equal(base.envio, undefined);

// ── alterar não muta e guarda só o que mudou ──
const alterado = alterarEnvio(base, { testemunhaIds: [3] });
assert.notEqual(alterado, base);
assert.equal(base.envio, undefined);
assert.deepEqual(alterado.envio, { testemunhaIds: [3] });
assert.deepEqual(alterarEnvio(alterado, { testemunhasExtras: [{ email: "t@x.com", name: "T" }] }).envio, {
  testemunhaIds: [3],
  testemunhasExtras: [{ email: "t@x.com", name: "T" }],
});

// ── abrir: formatos antigos e padrões ──
assert.deepEqual(normalizarFormData(null), DADOS_INICIAIS);
const antigo = normalizarFormData({
  participacao: { tem_participacao: true, para_quem: "Carla Sócia", natureza: "indicacao", percentual_ou_valor: "5%" },
} as never);
assert.deepEqual(antigo.participacao.participantes, [{ nome: "Carla Sócia", natureza: "indicacao", percentual: undefined }]);
assert.equal(antigo.participacao.valor_tipo, "outro");
assert.equal(antigo.participacao.valor_outro, "5%");
const comEnvio = normalizarFormData({ ...DADOS_INICIAIS, ajustes_texto: { "2.2": { texto: "a", padrao: "b" } }, envio: { socioEscritorio: "x@y" } });
assert.deepEqual(comEnvio.ajustes_texto, { "2.2": { texto: "a", padrao: "b" } });
assert.equal(comEnvio.envio?.socioEscritorio, "x@y");
// vigência que morava no pró-labore vai para os acessórios, e o pró-labore fica sem ela
const vig = normalizarFormData({
  ...DADOS_INICIAIS,
  escopos: [{ tipo: "x", honorarios: [], pro_labore: { valor_total: 1, data_inicio: "2026-01-01", data_fim: "2026-12-31", duracao_meses: 12 } }],
} as never);
assert.equal(vig.acessorios.vigencia_inicio, "2026-01-01");
assert.equal(vig.escopos[0].pro_labore?.data_inicio, undefined);

// ── etapas 1 a 4: reabrir o rascunho devolve exatamente o que foi digitado ──
const etapas1a4 = {
  contratantes: [
    { tipo: "PF", nome: "Ana", nacionalidade: "Brasileiro(a)", cpf: "1", profissao: "x", estado_civil: "Solteiro(a)", email: "a@x.com",
      endereco: "Av. Afonso Pena, n. 100, sala 2, Centro, Belo Horizonte/MG, CEP 30130-009" },
    { tipo: "PJ", razao_social: "Beta Ltda", cnpj: "2", email: "b@x.com", endereco: "Rua Livre 5" },
  ],
  incluir_partes_relacionadas: true,
  escopos: [{ tipo: "consultivo", honorarios: { fixo: { valor_total: 100 } }, pro_labore: { valor_total: 5 } }],
  acessorios: {
    tem_reembolso: false,
    reembolso_limitado: true,
    descricao_limitacao_reembolso: "até R$ 100",
    tem_penalidade_inadimplemento: false,
    valor_diligencia: 50,
    valor_km: 2,
    criterio_extincao_exito: "trânsito em julgado",
    clausulas_adicionais: "Primeira\nSegunda",
    vigencia_inicio: "2026-01-01",
    vigencia_fim: "2026-12-31",
    vigencia_meses: 12,
  },
};
const reaberto = normalizarFormData(JSON.parse(JSON.stringify(normalizarFormData(etapas1a4 as never))));
assert.deepEqual(reaberto.contratantes, etapas1a4.contratantes);
assert.deepEqual(reaberto.acessorios, etapas1a4.acessorios);
assert.deepEqual(reaberto.escopos, etapas1a4.escopos);
assert.equal(reaberto.incluir_partes_relacionadas, true);

// ── formato versionado: todo snapshot traz a versão; sem número = formato anterior, convertido ao abrir ──
assert.equal(DADOS_INICIAIS.versao_formato, VERSAO_FORMATO);
assert.equal(normalizarFormData(null).versao_formato, VERSAO_FORMATO);
assert.equal(normalizarFormData({ ...etapas1a4, versao_formato: undefined } as never).versao_formato, VERSAO_FORMATO);
// formato 1 (sem número): vigência no pró-labore e participação em para_quem viram o formato atual
const v1 = normalizarFormData({
  ...etapas1a4,
  acessorios: { tem_reembolso: true, reembolso_limitado: false, tem_penalidade_inadimplemento: true },
  escopos: [{ tipo: "x", honorarios: [], pro_labore: { valor_total: 1, data_inicio: "2026-02-01", duracao_meses: 6 } }],
  participacao: { tem_participacao: true, para_quem: ["Carla Sócia"], natureza: "indicacao" },
} as never);
assert.equal(v1.versao_formato, VERSAO_FORMATO);
assert.equal(v1.acessorios.vigencia_inicio, "2026-02-01");
assert.equal(v1.participacao.participantes?.[0].nome, "Carla Sócia");
// idempotente: converter o já convertido não muda nada
assert.deepEqual(normalizarFormData(v1), v1);
assert.equal(JSON.stringify(normalizarFormData(JSON.parse(JSON.stringify(v1)))), JSON.stringify(v1));
// versão de um formato futuro não é rebaixada em silêncio
assert.equal(normalizarFormData({ ...etapas1a4, versao_formato: VERSAO_FORMATO + 1 } as never).versao_formato, VERSAO_FORMATO + 1);

// ── campo novo = um lugar: o que o wizard não conhece (backend à frente do front) sobrevive ao abrir ──
const comExtras = normalizarFormData({
  ...etapas1a4,
  campo_novo_topo: { a: 1 },
  acessorios: { ...etapas1a4.acessorios, campo_novo_acessorio: "x" },
  participacao: { tem_participacao: false, contato_financeiro_cliente: "Fulano", campo_novo_ficha: 7, para_quem: ["Carla"], natureza: "n", percentual_ou_valor: "5%" },
} as never) as unknown as Record<string, any>;
assert.deepEqual(comExtras.campo_novo_topo, { a: 1 });
assert.equal(comExtras.acessorios.campo_novo_acessorio, "x");
assert.equal(comExtras.participacao.contato_financeiro_cliente, "Fulano");
assert.equal(comExtras.participacao.campo_novo_ficha, 7);
// as chaves do formato antigo, já convertidas, não ficam ao lado das novas
for (const k of ["para_quem", "natureza", "percentual_ou_valor"]) assert.equal(k in comExtras.participacao, false, k);
assert.equal(comExtras.participacao.participantes[0].nome, "Carla");
assert.equal(JSON.stringify(normalizarFormData(comExtras as never)), JSON.stringify(comExtras)); // idempotente

// ── ficha interna ──
assert.equal(temFichaParaFinanceiro(undefined), false);
assert.equal(temFichaParaFinanceiro({ tem_participacao: false } as never), false);
assert.equal(temFichaParaFinanceiro({ tem_participacao: false, responsavel_gestao: "Carla Sócia" } as never), true);
const semPart = montarFicha("c1", dados({ participacao: { tem_participacao: false, valor_percentual: "9", responsavel_gestao: "Carla Sócia" } }), "objeto");
assert.equal(semPart.responsavel_gestao, "Carla Sócia");
assert.equal("valor_percentual" in semPart, false); // o que foi digitado antes de desligar não vai ao financeiro
const comPart = montarFicha("c1", dados({ participacao: { tem_participacao: true, valor_percentual: "9", valor_tipo: "percentual" } }), "objeto");
assert.equal(comPart.valor_percentual, "9");
assert.equal(comPart.cliente_nome, "Ana");
assert.equal(comPart.objeto_contrato, "objeto");

console.log("estadoWizard.ts ok");
