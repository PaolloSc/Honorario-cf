"use client";

import { useEffect, useState } from "react";
import type { Contratante, ContratantePF, ContratantePJ, ContratoFormData, EscopoItem } from "@/types/contract";
import { ESCOPO_LABELS } from "@/types/contract";
import { generateContract, updateContract, sendEmail, sendForSignature, sendParticipacao, listTestemunhas, type Testemunha } from "@/app/lib/api";

interface Step7EnvioProps {
  data: ContratoFormData;
  editContractId?: string;
  onSaveComplete?: (contractId: string) => void;
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

export default function Step7Envio({ data, editContractId, onSaveComplete }: Step7EnvioProps) {
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
  const isEdit = !!editContractId;

  // Testemunhas selecionadas (cadastro + avulsas) — entram no .docx e na assinatura
  const buildTestemunhas = () => [
    ...roster.filter((r) => selectedTestemunhaIds.includes(r.id)).map((t) => ({ nome: t.nome, email: t.email })),
    ...extraTestemunhas.map((t) => ({ nome: t.name, email: t.email })),
  ];

  useEffect(() => {
    listTestemunhas()
      .then((r) => setRoster(r.testemunhas))
      .catch(() => setRoster([]));
  }, []);

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

      const payload = { ...data, testemunhas: buildTestemunhas() };
      if (isEdit) {
        const result = await updateContract(editContractId, payload as unknown as Record<string, unknown>);
        if (!result.success) throw new Error(result.message || "Erro ao salvar contrato");
        resultContractId = result.contract_id;
      } else {
        const result = await generateContract(payload);
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
      if (data.participacao?.tem_participacao) {
        try {
          await sendParticipacao({
            contract_id: resultContractId,
            cliente_nome: getContratanteNome(data.contratantes[0]),
            objeto_contrato: buildObjetoContrato(data.escopos),
            valor_tipo: data.participacao.valor_tipo,
            valor_percentual: data.participacao.valor_percentual,
            valor_monetario: data.participacao.valor_monetario,
            valor_outro: data.participacao.valor_outro,
            para_quem: data.participacao.para_quem ?? [],
            natureza: data.participacao.natureza,
            responsavel_captacao: data.participacao.responsavel_captacao,
            responsavel_gestao: data.participacao.responsavel_gestao,
            contato_financeiro_nome: data.participacao.contato_financeiro_nome,
            contato_financeiro_email: data.participacao.contato_financeiro_email,
            contato_financeiro_telefone: data.participacao.contato_financeiro_telefone,
            base_tipo: data.participacao.base_tipo,
            base_escopo_index: data.participacao.base_escopo_index,
            base_honorario: data.participacao.base_honorario,
            base_label: data.participacao.base_label,
          });
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

      const payload = { ...data, testemunhas: buildTestemunhas() };
      if (isEdit) {
        const result = await updateContract(editContractId, payload as unknown as Record<string, unknown>);
        if (!result.success) throw new Error(result.message || "Erro ao salvar contrato");
        resultContractId = result.contract_id;
      } else {
        const result = await generateContract(payload);
        if (!result.success) throw new Error(result.message || "Erro ao gerar contrato");
        resultContractId = result.contract_id!;
      }

      setContractId(resultContractId);

      // Send participação sheet to financeiro if applicable
      if (data.participacao?.tem_participacao) {
        try {
          await sendParticipacao({
            contract_id: resultContractId,
            cliente_nome: getContratanteNome(data.contratantes[0]),
            objeto_contrato: buildObjetoContrato(data.escopos),
            valor_tipo: data.participacao.valor_tipo,
            valor_percentual: data.participacao.valor_percentual,
            valor_monetario: data.participacao.valor_monetario,
            valor_outro: data.participacao.valor_outro,
            para_quem: data.participacao.para_quem ?? [],
            natureza: data.participacao.natureza,
            responsavel_captacao: data.participacao.responsavel_captacao,
            responsavel_gestao: data.participacao.responsavel_gestao,
            contato_financeiro_nome: data.participacao.contato_financeiro_nome,
            contato_financeiro_email: data.participacao.contato_financeiro_email,
            contato_financeiro_telefone: data.participacao.contato_financeiro_telefone,
            base_tipo: data.participacao.base_tipo,
            base_escopo_index: data.participacao.base_escopo_index,
            base_honorario: data.participacao.base_honorario,
            base_label: data.participacao.base_label,
          });
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
      const signatarios = data.contratantes.map((c) => ({
        email: c.email,
        name: getContratanteNome(c),
        role: "Contratante",
      }));

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
    if (contractId && onSaveComplete) {
      onSaveComplete(contractId);
    }
  };

  // Seletor de testemunhas — usado antes de gerar (entram no .docx) e depois (assinatura)
  const testemunhasSelector = (
    <div className="w-full mb-2 p-4 rounded-lg bg-purple-50 border border-purple-200">
      <h4 className="text-sm font-medium text-purple-900 mb-2">Testemunhas</h4>
      <p className="text-xs text-purple-700 mb-3">
        <strong>Testemunha 1 (financeiro)</strong> é incluída automaticamente. Selecione outras do cadastro ou adicione avulsas. As selecionadas entram no contrato e na assinatura.
      </p>

      {roster.length > 0 && (
        <div className="space-y-1 mb-3">
          {roster.map((t) => (
            <label key={t.id} className="flex items-center gap-2 text-sm bg-white px-3 py-1.5 rounded border border-purple-100 cursor-pointer">
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
            <div key={i} className="flex items-center gap-2 text-sm bg-white px-3 py-1.5 rounded border border-purple-100">
              <span className="flex-1">{t.name} ({t.email}) <em className="text-purple-500">avulsa</em></span>
              <button
                onClick={() => setExtraTestemunhas((prev) => prev.filter((_, idx) => idx !== i))}
                className="text-red-500 hover:text-red-700 text-xs font-medium"
              >
                Remover
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <input
          type="text"
          value={newTestemunhaNome}
          onChange={(e) => setNewTestemunhaNome(e.target.value)}
          placeholder="Nome da testemunha"
          className="flex-1 px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-purple-300"
        />
        <input
          type="email"
          value={newTestemunhaEmail}
          onChange={(e) => setNewTestemunhaEmail(e.target.value)}
          placeholder="email@exemplo.com"
          className="flex-1 px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-purple-300"
        />
        <button
          onClick={() => {
            if (!newTestemunhaEmail.trim()) return;
            setExtraTestemunhas((prev) => [...prev, { email: newTestemunhaEmail.trim(), name: newTestemunhaNome.trim() || newTestemunhaEmail.trim() }]);
            setNewTestemunhaEmail("");
            setNewTestemunhaNome("");
          }}
          disabled={!newTestemunhaEmail.trim()}
          className="px-3 py-1.5 bg-purple-600 text-white text-sm rounded hover:bg-purple-700 disabled:opacity-50 transition"
        >
          Adicionar
        </button>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">
        {isEdit ? "Salvar Nova Versão" : "Revisão e Envio"}
      </h2>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="font-medium text-blue-900 mb-2">Resumo do Contrato</h3>
        <div className="text-sm text-blue-800 space-y-1">
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
                <label className="block text-xs text-blue-700 mb-0.5">
                  {r.nome || `Contratante ${i + 1}`}
                </label>
                <input
                  type="email"
                  value={r.email}
                  onChange={(e) => updateRecipient(i, e.target.value)}
                  disabled={status === "sent_email" || status === "success"}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:bg-gray-100"
                  placeholder="email@exemplo.com"
                />
              </div>
            ))}
          </div>
        </div>
      </div>

      {isEdit && status === "idle" && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <h3 className="font-medium text-amber-900 mb-2">Modo de edição</h3>
          <p className="text-sm text-amber-800">
            Uma nova versão será criada. O histórico anterior será mantido.
          </p>
        </div>
      )}

      {!isEdit && status === "idle" && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <h3 className="font-medium text-amber-900 mb-2">Próximos passos</h3>
          <ol className="text-sm text-amber-800 space-y-1 list-decimal list-inside">
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
              ? "bg-green-50 text-green-800 border border-green-200"
              : status === "sent_email"
              ? "bg-green-50 text-green-800 border border-green-200"
              : status === "error"
              ? "bg-red-50 text-red-800 border border-red-200"
              : "bg-blue-50 text-blue-800 border border-blue-200"
          }`}
        >
          {message}
        </div>
      )}

      {emailWarning && (
        <div className="p-4 rounded-lg bg-amber-50 text-amber-800 border border-amber-200">
          {emailWarning}
        </div>
      )}

      {participacaoWarning && (
        <div className="p-4 rounded-lg bg-amber-50 text-amber-800 border border-amber-200">
          {participacaoWarning}
        </div>
      )}

      <div className="flex gap-4 flex-wrap">
        {/* Initial actions - before save */}
        {status === "idle" && (
          <>
            {testemunhasSelector}
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
          <button disabled className="px-4 py-2 bg-gray-200 text-gray-500 rounded-lg cursor-not-allowed">
            {status === "generating" ? "Salvando..." : "Enviando..."}
          </button>
        )}

        {/* After save/email success - show signature button */}
        {status === "sent_email" && contractId && (
          <>
            {/* Additional lawyers section */}
            <div className="w-full mb-2 p-4 rounded-lg bg-purple-50 border border-purple-200">
              <h4 className="text-sm font-medium text-purple-900 mb-2">
                Advogados adicionais para assinatura (opcional)
              </h4>
              <p className="text-xs text-purple-700 mb-3">
                O advogado logado já será incluído automaticamente. Adicione outros se necessário.
              </p>
              {additionalLawyers.length > 0 && (
                <div className="space-y-1 mb-3">
                  {additionalLawyers.map((lawyer, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm bg-white px-3 py-1.5 rounded border border-purple-100">
                      <span className="flex-1">{lawyer.name} ({lawyer.email})</span>
                      <button
                        onClick={() => handleRemoveLawyer(i)}
                        className="text-red-500 hover:text-red-700 text-xs font-medium"
                      >
                        Remover
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newLawyerName}
                  onChange={(e) => setNewLawyerName(e.target.value)}
                  placeholder="Nome do advogado"
                  className="flex-1 px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-purple-300"
                />
                <input
                  type="email"
                  value={newLawyerEmail}
                  onChange={(e) => setNewLawyerEmail(e.target.value)}
                  placeholder="email@exemplo.com"
                  className="flex-1 px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-purple-300"
                />
                <button
                  onClick={handleAddLawyer}
                  disabled={!newLawyerEmail.trim()}
                  className="px-3 py-1.5 bg-purple-600 text-white text-sm rounded hover:bg-purple-700 disabled:opacity-50 transition"
                >
                  Adicionar
                </button>
              </div>
            </div>

            {testemunhasSelector}

            <button
              onClick={handleSendForSignature}
              disabled={isSubmitting}
              className="px-4 py-2 bg-accent text-white rounded-lg hover:opacity-90 disabled:opacity-50 transition"
            >
              Enviar para Assinatura Digital
            </button>

            <button
              onClick={handleGoToContract}
              className="px-4 py-2 border border-border text-foreground rounded-lg hover:bg-gray-50 transition"
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
            className="px-4 py-2 border border-border text-foreground rounded-lg hover:bg-gray-50 transition"
          >
            Tentar Novamente
          </button>
        )}
      </div>
    </div>
  );
}
