"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Contratante, ContratantePF, ContratantePJ, ContratoFormData, EscopoItem, Participacao } from "@/types/contract";
import { ESCOPO_LABELS } from "@/types/contract";
import { generateContract, updateContract, sendEmail, sendForSignature, sendParticipacao, listTestemunhas, listColaboradores, previewContract, reviewContract, type Testemunha } from "@/app/lib/api";

interface Step7EnvioProps {
  data: ContratoFormData;
  editContractId?: string;
  onSaveComplete?: (contractId: string) => void;
  onDataChange?: (data: ContratoFormData) => void;
  // Levantado pro ContractWizard (que não desmonta ao trocar de passo) — sem isso,
  // sair do Step 7 e voltar reseta o histórico de "Aplicar correção" pra vazio,
  // mesmo com o texto já corrigido continuando lá.
  correcoesAplicadas: Array<{ trecho: string; sugestao: string }>;
  onCorrecoesAplicadasChange: (updater: (prev: Array<{ trecho: string; sugestao: string }>) => Array<{ trecho: string; sugestao: string }>) => void;
}

// Os campos de participação só entram no payload quando o toggle está ligado: o
// wizard preserva o que foi digitado antes de desligá-lo, e mandá-los assim faria o
// financeiro receber uma participação que o contrato não tem.
function buildFichaPayload(contractId: string, data: ContratoFormData) {
  const p = data.participacao;
  return {
    contract_id: contractId,
    cliente_nome: getContratanteNome(data.contratantes[0]),
    objeto_contrato: buildObjetoContrato(data.escopos),
    categoria_cliente: p.categoria_cliente,
    etiquetas: p.etiquetas ?? [],
    listas_transmissao: p.listas_transmissao ?? [],
    // Contato financeiro do cliente e responsável pela gestão do contrato
    // independem de haver participação.
    contato_financeiro_nome: p.contato_financeiro_nome,
    contato_financeiro_email: p.contato_financeiro_email,
    contato_financeiro_telefone: p.contato_financeiro_telefone,
    responsavel_gestao: p.responsavel_gestao,
    ...(p.tem_participacao
      ? {
          valor_tipo: p.valor_tipo,
          valor_percentual: p.valor_percentual,
          valor_monetario: p.valor_monetario,
          valor_outro: p.valor_outro,
          participantes: p.participantes ?? [],
          responsavel_captacao: p.responsavel_captacao,
          base_tipo: p.base_tipo,
          base_escopo_index: p.base_escopo_index,
          base_honorario: p.base_honorario,
          base_label: p.base_label,
        }
      : {}),
  };
}

// A ficha vai ao financeiro quando há participação, cadastro do Legal One,
// contato financeiro ou responsável pela gestão preenchidos — contratos sem
// participação também precisam ser lançados, e esses campos agora independem
// da participação.
function temFichaParaFinanceiro(p?: Participacao): p is Participacao {
  if (!p) return false;
  return Boolean(
    p.tem_participacao ||
      p.categoria_cliente ||
      p.etiquetas?.length ||
      p.listas_transmissao?.length ||
      p.contato_financeiro_nome ||
      p.contato_financeiro_email ||
      p.contato_financeiro_telefone ||
      p.responsavel_gestao
  );
}

function getContratanteNome(c: Contratante): string {
  if (c.tipo === "PF") return (c as ContratantePF).nome;
  return (c as ContratantePJ).razao_social;
}

function buildObjetoContrato(escopos: EscopoItem[]): string {
  return escopos
    .map((e) => {
      const parts: string[] = [];

      // Main label
      const label = ESCOPO_LABELS[e.tipo] || e.tipo || "";
      if (label && e.tipo !== "outro") parts.push(label);

      // Custom description
      if (e.descricao_custom) parts.push(e.descricao_custom);

      // Process number
      if (e.numero_autos) parts.push(`Processo: ${e.numero_autos}`);

      // Demands
      if (e.demandas) parts.push(`Demandas: ${e.demandas}`);

      // People/assets
      if (e.pessoas_patrimonios) parts.push(`Pessoas/Patrimônios: ${e.pessoas_patrimonios}`);

      // Restructuring type
      if (e.tipo_reestruturacao) parts.push(`Reestruturação: ${e.tipo_reestruturacao}`);

      // Documents
      if (e.documentos) parts.push(`Documentos: ${e.documentos}`);

      // Legal opinion topic
      if (e.consulta) parts.push(`Consulta: ${e.consulta}`);

      // Memorial activities
      if (e.subtipo_memoriais) {
        const atividades: string[] = [];
        if (e.subtipo_memoriais.elaboracao_memoriais) atividades.push("Elaboração de Memoriais");
        if (e.subtipo_memoriais.despacho_memoriais) atividades.push("Despacho de Memoriais");
        if (e.subtipo_memoriais.sustentacao_oral_relator) atividades.push("Sustentação oral c/ Relator");
        if (e.subtipo_memoriais.sustentacao_oral_todos_julgadores) atividades.push("Sustentação oral c/ todos os julgadores");
        if (atividades.length > 0) parts.push(`Atividades: ${atividades.join(", ")}`);
      }

      return parts.join(" | ");
    })
    .filter(Boolean)
    .join("\n");
}

function escapeHtmlAttr(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

// Marca no HTML da prévia os trechos apontados pela revisão de IA, pra dar pra ver
// a divergência no lugar em vez de só numa lista separada. Casamento por substring —
// suficiente pq o trecho citado pela IA normalmente é cópia literal do texto gerado.
// O número sobrescrito liga o trecho ao card correspondente na lista abaixo; o
// title nativo (a prévia roda numa iframe sandbox sem script) mostra o motivo ao passar o mouse.
//
// Os trechos apontados podem se sobrepor (ex.: "junto aos credor" dentro de
// "necessita de acompanhamento junto aos credor"). Substituir um-a-um com
// string.split/join quebra o HTML quando um trecho já inserido (incluindo a tag
// <mark> e o title) contém o texto do próximo — por isso resolve-se todas as
// posições no HTML ORIGINAL primeiro, descarta sobreposições e só então monta a
// string final numa única passada.
function highlightFindings(
  html: string,
  findings: Array<{ trecho: string; problema: string; sugestao: string }>
): string {
  const matches = findings
    .map((f, i) => {
      const t = f.trecho.trim();
      const start = t ? html.indexOf(t) : -1;
      return start === -1 ? null : { start, end: start + t.length, f, t, i };
    })
    .filter((m): m is NonNullable<typeof m> => m !== null)
    .sort((a, b) => a.start - b.start);

  const nonOverlapping: typeof matches = [];
  let lastEnd = -1;
  for (const m of matches) {
    if (m.start < lastEnd) continue;
    nonOverlapping.push(m);
    lastEnd = m.end;
  }

  let out = "";
  let cursor = 0;
  for (const { start, end, f, t, i } of nonOverlapping) {
    out += html.slice(cursor, start);
    const tooltip = escapeHtmlAttr(`Problema: ${f.problema} — Sugestão: ${f.sugestao}`);
    out +=
      `<mark title="${tooltip}" style="background:rgba(180,83,9,0.14);border-bottom:2px dotted #B45309;` +
      `border-radius:2px;padding:0 1px;cursor:help">${t}</mark>` +
      `<sup style="font-size:10px;font-weight:700;color:#B45309;margin-left:1px">${i + 1}</sup>`;
    cursor = end;
  }
  out += html.slice(cursor);
  return out;
}

// Procura o campo aberto do formulário que contém o trecho apontado e devolve os
// dados com a sugestão aplicada ali (primeira ocorrência). null se não achar —
// o botão "Aplicar correção" só aparece quando isto resolve, pra nunca prometer
// um clique que não faz nada.
function applyFix(data: ContratoFormData, trecho: string, sugestao: string): ContratoFormData | null {
  const t = trecho.trim();
  if (!t) return null;

  for (let i = 0; i < data.contratantes.length; i++) {
    const c = data.contratantes[i];
    if (c.tipo === "PF" && c.profissao?.includes(t)) {
      const contratantes = [...data.contratantes];
      contratantes[i] = { ...c, profissao: c.profissao.replace(t, sugestao) };
      return { ...data, contratantes };
    }
  }

  const escopoFields = [
    "descricao_custom",
    "demandas",
    "pessoas_patrimonios",
    "tipo_reestruturacao",
    "documentos",
    "consulta",
  ] as const;
  for (let i = 0; i < data.escopos.length; i++) {
    const e = data.escopos[i];
    for (const field of escopoFields) {
      const val = e[field];
      if (typeof val === "string" && val.includes(t)) {
        const escopos = [...data.escopos];
        escopos[i] = { ...e, [field]: val.replace(t, sugestao) };
        return { ...data, escopos };
      }
    }
    if (e.permuta?.descricao?.includes(t)) {
      const escopos = [...data.escopos];
      escopos[i] = { ...e, permuta: { ...e.permuta, descricao: e.permuta.descricao.replace(t, sugestao) } };
      return { ...data, escopos };
    }
    if (e.permuta?.forma_pagamento_torna?.includes(t)) {
      const escopos = [...data.escopos];
      escopos[i] = {
        ...e,
        permuta: { ...e.permuta, forma_pagamento_torna: e.permuta.forma_pagamento_torna.replace(t, sugestao) },
      };
      return { ...data, escopos };
    }
  }

  const acessoriosFields = ["descricao_limitacao_reembolso", "criterio_extincao_exito", "clausulas_adicionais"] as const;
  for (const field of acessoriosFields) {
    const val = data.acessorios[field];
    if (typeof val === "string" && val.includes(t)) {
      return { ...data, acessorios: { ...data.acessorios, [field]: val.replace(t, sugestao) } };
    }
  }

  return null;
}

export default function Step7Envio({
  data,
  editContractId,
  onSaveComplete,
  onDataChange,
  correcoesAplicadas,
  onCorrecoesAplicadasChange,
}: Step7EnvioProps) {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [status, setStatus] = useState<"idle" | "generating" | "sending" | "sent_email" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [contractId, setContractId] = useState<string | null>(editContractId || null);
  const [participacaoWarning, setParticipacaoWarning] = useState("");
  const [emailWarning, setEmailWarning] = useState("");
  const [recipients, setRecipients] = useState<Array<{ email: string; nome: string }>>(
    () => data.contratantes.map((c) => ({ email: c.email || "", nome: getContratanteNome(c) }))
  );
  const [signatureSent, setSignatureSent] = useState(false);
  const [additionalLawyers, setAdditionalLawyers] = useState<Array<{email: string; name: string}>>([]);
  const [newLawyerEmail, setNewLawyerEmail] = useState("");
  const [newLawyerName, setNewLawyerName] = useState("");
  // Testemunhas: roster + selecionadas + avulsas (Lilian/Testemunha 1 injetada no backend)
  const [roster, setRoster] = useState<Testemunha[]>([]);
  const [selectedTestemunhaIds, setSelectedTestemunhaIds] = useState<number[]>([]);
  const [extraTestemunhas, setExtraTestemunhas] = useState<Array<{email: string; name: string}>>([]);
  const [newTestemunhaNome, setNewTestemunhaNome] = useState("");
  const [newTestemunhaEmail, setNewTestemunhaEmail] = useState("");
  // Colaboradores do escritorio: autopreenchimento de advogados e testemunhas.
  const [colaboradores, setColaboradores] = useState<Array<{ name: string; email: string; role: string }>>([]);
  const isEdit = !!editContractId;
  // Prévia de como o contrato fica no Word/PDF (mesmo preview da tela do contrato).
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  // Prévia gerada junto da revisão (antes de existir contractId — cobre a criação).
  const [reviewPreviewHtml, setReviewPreviewHtml] = useState<string | null>(null);
  // Varredura de português/padrão via DeepSeek, roda sozinha ao chegar neste passo.
  const [reviewFindings, setReviewFindings] = useState<Array<{ trecho: string; problema: string; sugestao: string }>>([]);
  const [reviewStatus, setReviewStatus] = useState<"idle" | "checking" | "done" | "error">("idle");
  // Indice do achado com "Aplicar correção" em andamento (desabilita só aquele botão).
  const [applyingIndex, setApplyingIndex] = useState<number | null>(null);

  useEffect(() => {
    listTestemunhas()
      .then((r) => setRoster(r.testemunhas))
      .catch(() => setRoster([]));
    listColaboradores()
      .then((r) => setColaboradores(r.colaboradores))
      .catch(() => setColaboradores([]));
  }, []);

  useEffect(() => {
    // Só faz sentido revisar o texto ainda não gerado (criação). Em edição o
    // conteúdo já existente pode ser revisado do mesmo jeito, então roda sempre.
    setReviewStatus("checking");
    reviewContract(data)
      .then((r) => {
        if (r.preview_html) setReviewPreviewHtml(r.preview_html);
        if (!r.enabled) {
          setReviewStatus("idle");
          return;
        }
        setReviewFindings(r.findings);
        setReviewStatus("done");
      })
      .catch(() => setReviewStatus("error"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Aplica a sugestão da IA no campo aberto de onde ela veio e reroda a revisão,
  // pra prévia e lista já saírem atualizadas sem a pessoa ter que digitar nada.
  const handleApplyFix = async (index: number) => {
    const finding = reviewFindings[index];
    const updated = applyFix(data, finding.trecho, finding.sugestao);
    if (!updated || !onDataChange) return;

    onDataChange(updated);
    setApplyingIndex(index);
    // Marca como corrigido imediatamente — o campo já foi alterado nesse ponto,
    // então a confirmação (check) aparece na hora, antes mesmo da revisão nova voltar.
    onCorrecoesAplicadasChange((prev) => [...prev, { trecho: finding.trecho, sugestao: finding.sugestao }]);
    try {
      const r = await reviewContract(updated);
      if (r.preview_html) setReviewPreviewHtml(r.preview_html);
      setReviewFindings(r.enabled ? r.findings : []);
    } catch {
      // Se a nova revisão falhar, o campo já foi corrigido — só tira o achado da lista.
      setReviewFindings((prev) => prev.filter((_, i) => i !== index));
    } finally {
      setApplyingIndex(null);
    }
  };

  useEffect(() => {
    // Edit: contrato ja existe -> preview imediato. Criacao: carrega apos gerar.
    // ponytail: refetch em cada mudanca de status cobre "nova versao salva".
    if (!contractId || status === "generating" || status === "sending") return;
    previewContract(contractId).then(setPreviewHtml).catch(() => setPreviewHtml(null));
  }, [contractId, status]);

  const handleAddLawyer = () => {
    if (!newLawyerEmail.trim()) return;
    setAdditionalLawyers((prev) => [...prev, { email: newLawyerEmail.trim(), name: newLawyerName.trim() || newLawyerEmail.trim() }]);
    setNewLawyerEmail("");
    setNewLawyerName("");
  };

  const handleRemoveLawyer = (index: number) => {
    setAdditionalLawyers((prev) => prev.filter((_, i) => i !== index));
  };

  const updateRecipient = (index: number, email: string) => {
    setRecipients((prev) => prev.map((r, i) => (i === index ? { ...r, email } : r)));
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setStatus("generating");
    setMessage(isEdit ? "Salvando nova versão..." : "Gerando contrato...");

    try {
      let resultContractId: string;

      if (isEdit) {
        const result = await updateContract(editContractId, data as unknown as Record<string, unknown>);
        if (!result.success) throw new Error(result.message || "Erro ao salvar contrato");
        resultContractId = result.contract_id;
      } else {
        const result = await generateContract(data);
        if (!result.success) throw new Error(result.message || "Erro ao gerar contrato");
        resultContractId = result.contract_id!;
      }

      setContractId(resultContractId);
      setStatus("sending");
      setMessage("Enviando e-mail...");

      const destinatarios = recipients.filter((r) => r.email.trim());
      if (destinatarios.length === 0) {
        throw new Error("Nenhum e-mail de destinatário informado.");
      }

      const falhas: string[] = [];
      for (const dest of destinatarios) {
        const email = dest.email.trim();
        try {
          const emailResult = await sendEmail({
            contract_id: resultContractId,
            destinatario_email: email,
            destinatario_nome: dest.nome || email,
            assunto: "Contrato de Honorários - C&F Advogados - Para Conferência",
          });
          if (!emailResult.success) {
            falhas.push(`${email}: ${emailResult.message || "erro"}`);
          }
        } catch (err) {
          const detail = err instanceof Error ? err.message : "erro desconhecido";
          falhas.push(`${email}: ${detail}`);
        }
      }

      if (falhas.length === destinatarios.length) {
        throw new Error(`Erro ao enviar e-mail: ${falhas.join("; ")}`);
      }
      if (falhas.length > 0) {
        setEmailWarning(`Alguns e-mails não foram enviados: ${falhas.join("; ")}`);
      }

      // Send participação sheet to financeiro if applicable
      if (temFichaParaFinanceiro(data.participacao)) {
        try {
          await sendParticipacao(buildFichaPayload(resultContractId, data));
        } catch (err) {
          const detail = err instanceof Error ? err.message : "";
          setParticipacaoWarning(`Ficha de participação não enviada ao financeiro. ${detail}`);
        }
      }

      setStatus("sent_email");
      setMessage(
        isEdit
          ? "Nova versão gerada e enviada por e-mail com sucesso! Agora você pode enviar para assinatura digital ou voltar para a lista."
          : "Contrato gerado e enviado por e-mail com sucesso! Agora você pode enviar para assinatura digital ou voltar para a lista."
      );
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Erro desconhecido");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSaveOnly = async () => {
    setIsSubmitting(true);
    setStatus("generating");
    setMessage(isEdit ? "Salvando nova versão..." : "Gerando contrato...");

    try {
      let resultContractId: string;

      if (isEdit) {
        const result = await updateContract(editContractId, data as unknown as Record<string, unknown>);
        if (!result.success) throw new Error(result.message || "Erro ao salvar contrato");
        resultContractId = result.contract_id;
      } else {
        const result = await generateContract(data);
        if (!result.success) throw new Error(result.message || "Erro ao gerar contrato");
        resultContractId = result.contract_id!;
      }

      setContractId(resultContractId);

      // Send participação sheet to financeiro if applicable
      if (temFichaParaFinanceiro(data.participacao)) {
        try {
          await sendParticipacao(buildFichaPayload(resultContractId, data));
        } catch (err) {
          const detail = err instanceof Error ? err.message : "";
          setParticipacaoWarning(`Ficha de participação não enviada ao financeiro. ${detail}`);
        }
      }

      setStatus("sent_email");
      setMessage(
        isEdit
          ? "Nova versão salva com sucesso! Você pode enviar para assinatura ou voltar para a lista."
          : "Contrato gerado com sucesso! Você pode enviar para assinatura ou voltar para a lista."
      );
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Erro desconhecido");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSendForSignature = async () => {
    if (!contractId) return;

    setIsSubmitting(true);
    setStatus("sending");
    setMessage("Enviando para assinatura digital...");

    try {
      // PJ com mais de um representante legal: cada administrador assina
      // (ha empresas cuja assinatura so vale com dois administradores).
      const signatarios = data.contratantes.flatMap((c) => {
        const reps = c.tipo === "PJ" ? (c as ContratantePJ).representantes ?? [] : [];
        const assinantes = reps.filter((r) => r.nome && r.email);
        if (assinantes.length === 0) {
          return [{ email: c.email, name: getContratanteNome(c), role: "Contratante" }];
        }
        return assinantes.map((r) => ({
          email: r.email!,
          name: `${r.nome} (${getContratanteNome(c)})`,
          role: "Contratante",
        }));
      });

      // Add additional lawyers as "Advogado" role
      for (const lawyer of additionalLawyers) {
        signatarios.push({
          email: lawyer.email,
          name: lawyer.name,
          role: "Advogado",
        });
      }

      // Testemunhas: do roster + avulsas (Testemunha 1 = financeiro e' injetada no backend)
      for (const t of roster.filter((r) => selectedTestemunhaIds.includes(r.id))) {
        signatarios.push({ email: t.email, name: t.nome, role: "Testemunha" });
      }
      for (const t of extraTestemunhas) {
        signatarios.push({ email: t.email, name: t.name, role: "Testemunha" });
      }

      const result = await sendForSignature({
        contract_id: contractId,
        signatarios,
      });

      if (!result.success) {
        throw new Error(result.message || "Erro ao enviar para assinatura");
      }

      setSignatureSent(true);
      setStatus("success");
      setMessage("Documento enviado para assinatura digital com sucesso!");

      // Navigate to detail page after signature is sent
      if (onSaveComplete) {
        setTimeout(() => onSaveComplete(contractId), 2000);
      }
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Erro desconhecido");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoToContract = () => {
    if (!contractId) return;
    // Fluxo de criacao (page.tsx) nao passa onSaveComplete; navega direto.
    if (onSaveComplete) onSaveComplete(contractId);
    else router.push(`/contracts/${contractId}`);
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">
        {isEdit ? "Salvar Nova Versão" : "Revisão e Envio"}
      </h2>

      <div className="bg-primary/[0.08] border border-primary rounded-lg p-4">
        <h3 className="font-medium text-primary-dark mb-2">Resumo do Contrato</h3>
        <div className="text-sm text-foreground space-y-1">
          <p>
            <strong>Contratante(s):</strong> {data.contratantes.length}
          </p>
          <p>
            <strong>Escopo(s):</strong> {data.escopos.length}
          </p>
          <p>
            <strong>E-mail(s) para envio:</strong>
          </p>
          <div className="space-y-2 mt-1">
            {recipients.map((r, i) => (
              <div key={i}>
                <label className="block text-xs text-muted mb-0.5">
                  {r.nome || `Contratante ${i + 1}`}
                </label>
                <input
                  type="email"
                  value={r.email}
                  onChange={(e) => updateRecipient(i, e.target.value)}
                  disabled={status === "sent_email" || status === "success"}
                  className="w-full px-3 py-2 border border-border bg-card text-foreground rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:bg-border/35 disabled:border-muted disabled:text-muted"
                  placeholder="email@exemplo.com"
                />
              </div>
            ))}
          </div>
        </div>
      </div>

      {reviewStatus === "checking" && (
        <div className="bg-card border border-border rounded-lg p-4 text-sm text-muted">
          Verificando português e padrão do contrato com IA...
        </div>
      )}

      {reviewStatus === "error" && (
        <div className="bg-warning/[0.1] border border-warning rounded-lg p-4 text-sm text-foreground">
          Não foi possível concluir a verificação de português. Você pode revisar manualmente e prosseguir.
        </div>
      )}

      {reviewStatus === "done" && reviewFindings.length === 0 && (
        <div className="bg-primary/[0.08] border border-primary rounded-lg p-4 text-sm text-primary-dark">
          Nenhuma divergência de português ou padrão encontrada.
        </div>
      )}

      {reviewStatus === "done" && reviewFindings.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
          <div className="flex items-start justify-between gap-3 pb-3.5 mb-3.5 border-b border-border">
            <div className="flex items-start gap-2.5">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="mt-0.5 shrink-0">
                <path d="M12 3.5 2.5 20h19L12 3.5Z" stroke="#B45309" strokeWidth="1.8" strokeLinejoin="round" />
                <path d="M12 10v4.5" stroke="#B45309" strokeWidth="1.8" strokeLinecap="round" />
                <circle cx="12" cy="17.3" r="1" fill="#B45309" />
              </svg>
              <div>
                <p className="text-[15px] font-semibold text-primary-dark">Divergências encontradas</p>
                <p className="text-xs text-muted mt-0.5">Revisão de português via IA — revise antes de gerar</p>
              </div>
            </div>
            <span className="shrink-0 inline-flex items-center justify-center min-w-[26px] h-[26px] px-2 rounded-full text-[13px] font-bold text-warning bg-warning/20 border border-warning">
              {reviewFindings.length}
            </span>
          </div>

          <div className="flex flex-col gap-2.5">
            {reviewFindings.map((f, i) => {
              const fixable = !!onDataChange && applyFix(data, f.trecho, f.sugestao) !== null;
              return (
                <div key={i} className="flex gap-3 p-3 border border-border rounded-[10px] bg-background">
                  <div className="shrink-0 w-[22px] h-[22px] rounded-full bg-warning/[0.22] text-warning text-xs font-bold flex items-center justify-center mt-px border border-warning">
                    {i + 1}
                  </div>
                  <div className="min-w-0 flex-1 text-[13px]">
                    <span className="inline-block font-mono text-xs text-foreground bg-card border border-border rounded px-1.5 py-1 mb-2 leading-normal">
                      &ldquo;{f.trecho}&rdquo;
                    </span>
                    <div className="flex gap-1.5 items-start mt-1">
                      <span className="text-[11px] font-semibold uppercase tracking-wide text-warning shrink-0 pt-px">Problema</span>
                      <span className="text-foreground">{f.problema}</span>
                    </div>
                    <div className="flex gap-1.5 items-start mt-1">
                      <span className="text-[11px] font-semibold uppercase tracking-wide text-primary shrink-0 pt-px">Sugestão</span>
                      <span className="text-foreground">{f.sugestao}</span>
                    </div>
                    {fixable && (
                      <button
                        type="button"
                        onClick={() => handleApplyFix(i)}
                        disabled={applyingIndex !== null}
                        className="mt-2.5 inline-flex items-center gap-1.5 text-xs font-semibold text-primary-dark bg-primary/[0.16] border border-primary rounded-lg px-3 py-1.5 hover:bg-primary/25 transition-colors disabled:opacity-50 disabled:cursor-wait"
                      >
                        {applyingIndex === i ? (
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="animate-spin">
                            <path d="M12 3a9 9 0 1 0 9 9" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
                          </svg>
                        ) : (
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                            <path d="M20 6 9 17l-5-5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        )}
                        {applyingIndex === i ? "Aplicando..." : "Aplicar correção"}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {correcoesAplicadas.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-4 mb-6">
          <p className="text-sm font-semibold text-primary-dark mb-2">
            Correções aplicadas ({correcoesAplicadas.length})
          </p>
          <ul className="flex flex-col gap-1.5">
            {correcoesAplicadas.map((c, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-foreground">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="mt-0.5 shrink-0 text-primary">
                  <circle cx="12" cy="12" r="10" fill="currentColor" fillOpacity="0.22" stroke="currentColor" strokeOpacity="0.5" />
                  <path d="M8 12.5l2.5 2.5L16 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span>
                  <span className="line-through text-muted">{c.trecho}</span>
                  {" → "}
                  <span className="text-primary-dark">{c.sugestao}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {(previewHtml || reviewPreviewHtml) && (
        <div>
          <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
            <h3 className="font-medium">Prévia do contrato (como ficará no Word/PDF)</h3>
            {reviewFindings.length > 0 && (
              <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-warning bg-warning/[0.16] border border-warning rounded-full pl-2 pr-2.5 py-0.5">
                <span className="w-[11px] h-[11px] rounded-[3px] bg-warning/[0.28]" style={{ border: "1.5px dotted #B45309" }} />
                trecho sinalizado pela IA
              </span>
            )}
          </div>
          <div className="border border-border rounded-xl overflow-hidden bg-white">
            <iframe
              srcDoc={highlightFindings(previewHtml || reviewPreviewHtml || "", reviewFindings)}
              title="Prévia do contrato"
              sandbox=""
              className="w-full"
              style={{ height: "60vh" }}
            />
          </div>
        </div>
      )}

      {isEdit && status === "idle" && (
        <div className="bg-warning/[0.1] border border-warning rounded-lg p-4">
          <h3 className="font-medium text-warning mb-2">Modo de edição</h3>
          <p className="text-sm text-foreground">
            Uma nova versão será criada. O histórico anterior será mantido.
          </p>
        </div>
      )}

      {!isEdit && status === "idle" && (
        <div className="bg-warning/[0.1] border border-warning rounded-lg p-4">
          <h3 className="font-medium text-warning mb-2">Próximos passos</h3>
          <ol className="text-sm text-foreground space-y-1 list-decimal list-inside">
            <li>O contrato será gerado e enviado por e-mail para conferência</li>
            <li>Após confirmação, você poderá enviar para assinatura digital</li>
            <li>O contratante receberá um link para assinar via DocuSeal</li>
          </ol>
        </div>
      )}

      {message && (
        <div
          className={`p-4 rounded-lg ${
            status === "success"
              ? "bg-primary/[0.1] text-primary-dark border border-primary"
              : status === "sent_email"
              ? "bg-primary/[0.1] text-primary-dark border border-primary"
              : status === "error"
              ? "bg-danger/[0.1] text-danger border border-danger"
              : "bg-primary/[0.06] text-foreground border border-primary"
          }`}
        >
          {message}
        </div>
      )}

      {emailWarning && (
        <div className="p-4 rounded-lg bg-warning/[0.08] text-warning border border-warning">
          {emailWarning}
        </div>
      )}

      {participacaoWarning && (
        <div className="p-4 rounded-lg bg-warning/[0.08] text-warning border border-warning">
          {participacaoWarning}
        </div>
      )}

      <div className="flex gap-4 flex-wrap">
        {/* Initial actions - before save */}
        {status === "idle" && (
          <>
            <button
              onClick={handleSaveOnly}
              disabled={isSubmitting}
              className="px-4 py-2 border border-primary text-primary rounded-lg hover:bg-primary/5 disabled:opacity-50 transition"
            >
              {isEdit ? "Salvar Nova Versão" : "Apenas Gerar Contrato"}
            </button>

            <button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-50 transition"
            >
              {isEdit ? "Salvar e Enviar por E-mail" : "Gerar e Enviar por E-mail"}
            </button>
          </>
        )}

        {/* Loading state */}
        {(status === "generating" || status === "sending") && !signatureSent && (
          <button disabled className="px-4 py-2 bg-border/40 text-muted rounded-lg cursor-not-allowed">
            {status === "generating" ? "Salvando..." : "Enviando..."}
          </button>
        )}

        {/* After save/email success - show signature button */}
        {status === "sent_email" && contractId && (
          <>
            <datalist id="colaboradores-nomes">
              {colaboradores.map((c) => (
                <option key={c.email || c.name} value={c.name} label={c.email} />
              ))}
            </datalist>

            {/* Additional lawyers section */}
            <div className="w-full mb-2 p-4 rounded-lg bg-card border border-purple-300/40">
              <h4 className="text-sm font-medium text-purple-900 mb-2">
                Advogado(s) que assinarão pelo escritório (opcional)
              </h4>
              <p className="text-xs text-purple-700 mb-3">
                O <strong>C&amp;F</strong> assina como CONTRATADO. Quem preenche este formulário{" "}
                <strong>não</strong> é incluído automaticamente — selecione abaixo o(s) advogado(s)
                que devem assinar.
              </p>
              {additionalLawyers.length > 0 && (
                <div className="space-y-1 mb-3">
                  {additionalLawyers.map((lawyer, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm bg-card px-3 py-1.5 rounded border border-purple-300/40">
                      <span className="flex-1">{lawyer.name} ({lawyer.email})</span>
                      <button
                        onClick={() => handleRemoveLawyer(i)}
                        className="text-danger hover:opacity-80 text-xs font-medium"
                      >
                        Remover
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <input
                  type="text"
                  value={newLawyerName}
                  list="colaboradores-nomes"
                  onChange={(e) => {
                    setNewLawyerName(e.target.value);
                    const c = colaboradores.find((x) => x.name === e.target.value);
                    if (c?.email) setNewLawyerEmail(c.email);
                  }}
                  placeholder="Nome do advogado"
                  className="flex-1 min-w-40 px-3 py-1.5 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-purple-300"
                />
                <input
                  type="email"
                  value={newLawyerEmail}
                  onChange={(e) => setNewLawyerEmail(e.target.value)}
                  placeholder="email@exemplo.com"
                  className="flex-1 min-w-48 px-3 py-1.5 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-purple-300"
                />
                <button
                  onClick={handleAddLawyer}
                  disabled={!newLawyerEmail.trim()}
                  className="shrink-0 px-3 py-1.5 bg-purple-600 text-white text-sm rounded hover:bg-purple-700 disabled:opacity-50 transition"
                >
                  Adicionar
                </button>
              </div>
            </div>

            {/* Testemunhas section */}
            <div className="w-full mb-2 p-4 rounded-lg bg-card border border-purple-300/40">
              <h4 className="text-sm font-medium text-purple-900 mb-2">Testemunhas</h4>
              <p className="text-xs text-purple-700 mb-3">
                <strong>Testemunha 1 (financeiro)</strong> é incluída automaticamente. Selecione outras do cadastro ou adicione avulsas.
              </p>

              {roster.length > 0 && (
                <div className="space-y-1 mb-3">
                  {roster.map((t) => (
                    <label key={t.id} className="flex items-center gap-2 text-sm bg-card px-3 py-1.5 rounded border border-purple-300/40 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedTestemunhaIds.includes(t.id)}
                        onChange={(e) =>
                          setSelectedTestemunhaIds((prev) =>
                            e.target.checked ? [...prev, t.id] : prev.filter((id) => id !== t.id)
                          )
                        }
                      />
                      <span className="flex-1">{t.nome} ({t.email})</span>
                    </label>
                  ))}
                </div>
              )}

              {extraTestemunhas.length > 0 && (
                <div className="space-y-1 mb-3">
                  {extraTestemunhas.map((t, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm bg-card px-3 py-1.5 rounded border border-purple-300/40">
                      <span className="flex-1">{t.name} ({t.email}) <em className="text-accent">avulsa</em></span>
                      <button
                        onClick={() => setExtraTestemunhas((prev) => prev.filter((_, idx) => idx !== i))}
                        className="text-danger hover:opacity-80 text-xs font-medium"
                      >
                        Remover
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                <input
                  type="text"
                  value={newTestemunhaNome}
                  list="colaboradores-nomes"
                  onChange={(e) => {
                    setNewTestemunhaNome(e.target.value);
                    const c = colaboradores.find((x) => x.name === e.target.value);
                    if (c?.email) setNewTestemunhaEmail(c.email);
                  }}
                  placeholder="Nome da testemunha"
                  className="flex-1 min-w-40 px-3 py-1.5 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-purple-300"
                />
                <input
                  type="email"
                  value={newTestemunhaEmail}
                  onChange={(e) => setNewTestemunhaEmail(e.target.value)}
                  placeholder="email@exemplo.com"
                  className="flex-1 min-w-48 px-3 py-1.5 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-purple-300"
                />
                <button
                  onClick={() => {
                    if (!newTestemunhaEmail.trim()) return;
                    setExtraTestemunhas((prev) => [...prev, { email: newTestemunhaEmail.trim(), name: newTestemunhaNome.trim() || newTestemunhaEmail.trim() }]);
                    setNewTestemunhaEmail("");
                    setNewTestemunhaNome("");
                  }}
                  disabled={!newTestemunhaEmail.trim()}
                  className="shrink-0 px-3 py-1.5 bg-purple-600 text-white text-sm rounded hover:bg-purple-700 disabled:opacity-50 transition"
                >
                  Adicionar
                </button>
              </div>
            </div>

            <button
              onClick={handleSendForSignature}
              disabled={isSubmitting}
              className="px-4 py-2 bg-accent text-white rounded-lg hover:opacity-90 disabled:opacity-50 transition"
            >
              Enviar para Assinatura Digital
            </button>

            <button
              onClick={handleGoToContract}
              className="px-4 py-2 border border-border text-foreground rounded-lg hover:bg-background transition"
            >
              Ir para o Contrato
            </button>
          </>
        )}

        {/* After signature sent or final success */}
        {status === "success" && contractId && (
          <button
            onClick={handleGoToContract}
            className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-dark transition"
          >
            Ver Contrato
          </button>
        )}

        {/* Error state - allow retry */}
        {status === "error" && (
          <button
            onClick={() => { setStatus("idle"); setMessage(""); }}
            className="px-4 py-2 border border-border text-foreground rounded-lg hover:bg-background transition"
          >
            Tentar Novamente
          </button>
        )}
      </div>
    </div>
  );
}
