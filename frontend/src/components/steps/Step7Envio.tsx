"use client";

import { useState } from "react";
import type { Contratante, ContratantePF, ContratantePJ, ContratoFormData } from "@/types/contract";
import { generateContract, updateContract, sendEmail, sendForSignature, sendParticipacao } from "@/app/lib/api";

interface Step7EnvioProps {
  data: ContratoFormData;
  editContractId?: string;
  onSaveComplete?: (contractId: string) => void;
}

function getContratanteNome(c: Contratante): string {
  if (c.tipo === "PF") return (c as ContratantePF).nome;
  return (c as ContratantePJ).razao_social;
}

export default function Step7Envio({ data, editContractId, onSaveComplete }: Step7EnvioProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [status, setStatus] = useState<"idle" | "generating" | "sending" | "sent_email" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [contractId, setContractId] = useState<string | null>(editContractId || null);
  const [participacaoWarning, setParticipacaoWarning] = useState("");
  const [recipientEmail, setRecipientEmail] = useState(data.email_destinatario || data.contratantes[0]?.email || "");
  const [signatureSent, setSignatureSent] = useState(false);
  const isEdit = !!editContractId;

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setStatus("generating");
    setMessage(isEdit ? "Salvando nova versao..." : "Gerando contrato...");

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

      const emailResult = await sendEmail({
        contract_id: resultContractId,
        destinatario_email: recipientEmail,
        destinatario_nome: getContratanteNome(data.contratantes[0]),
        assunto: "Contrato de Honorários - C&F Advogados - Para Conferência",
      });

      if (!emailResult.success) {
        throw new Error(emailResult.message || "Erro ao enviar e-mail");
      }

      // Send participação sheet to financeiro if applicable
      if (data.participacao?.tem_participacao) {
        try {
          await sendParticipacao({
            contract_id: resultContractId,
            cliente_nome: getContratanteNome(data.contratantes[0]),
            percentual_ou_valor: data.participacao.percentual_ou_valor,
            para_quem: data.participacao.para_quem,
            natureza: data.participacao.natureza,
            responsavel_captacao: data.participacao.responsavel_captacao,
            responsavel_gestao: data.participacao.responsavel_gestao,
            contato_financeiro_cliente: data.participacao.contato_financeiro_cliente,
          });
        } catch (err) {
          const detail = err instanceof Error ? err.message : "";
          setParticipacaoWarning(`Ficha de participação não enviada ao financeiro. ${detail}`);
        }
      }

      setStatus("sent_email");
      setMessage(
        isEdit
          ? "Nova versao gerada e enviada por e-mail com sucesso! Agora voce pode enviar para assinatura digital ou voltar para a lista."
          : "Contrato gerado e enviado por e-mail com sucesso! Agora voce pode enviar para assinatura digital ou voltar para a lista."
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
    setMessage(isEdit ? "Salvando nova versao..." : "Gerando contrato...");

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
      if (data.participacao?.tem_participacao) {
        try {
          await sendParticipacao({
            contract_id: resultContractId,
            cliente_nome: getContratanteNome(data.contratantes[0]),
            percentual_ou_valor: data.participacao.percentual_ou_valor,
            para_quem: data.participacao.para_quem,
            natureza: data.participacao.natureza,
            responsavel_captacao: data.participacao.responsavel_captacao,
            responsavel_gestao: data.participacao.responsavel_gestao,
            contato_financeiro_cliente: data.participacao.contato_financeiro_cliente,
          });
        } catch (err) {
          const detail = err instanceof Error ? err.message : "";
          setParticipacaoWarning(`Ficha de participação não enviada ao financeiro. ${detail}`);
        }
      }

      setStatus("sent_email");
      setMessage(
        isEdit
          ? "Nova versao salva com sucesso! Voce pode enviar para assinatura ou voltar para a lista."
          : "Contrato gerado com sucesso! Voce pode enviar para assinatura ou voltar para a lista."
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

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">
        {isEdit ? "Salvar Nova Versao" : "Revisao e Envio"}
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
            <strong>E-mail para envio:</strong>
          </p>
          <input
            type="email"
            value={recipientEmail}
            onChange={(e) => setRecipientEmail(e.target.value)}
            disabled={status === "sent_email" || status === "success"}
            className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:bg-gray-100"
            placeholder="email@exemplo.com"
          />
        </div>
      </div>

      {isEdit && status === "idle" && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <h3 className="font-medium text-amber-900 mb-2">Modo de edicao</h3>
          <p className="text-sm text-amber-800">
            Uma nova versao sera criada. O historico anterior sera mantido.
          </p>
        </div>
      )}

      {!isEdit && status === "idle" && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <h3 className="font-medium text-amber-900 mb-2">Proximos passos</h3>
          <ol className="text-sm text-amber-800 space-y-1 list-decimal list-inside">
            <li>O contrato sera gerado e enviado por e-mail para conferencia</li>
            <li>Apos confirmacao, voce podera enviar para assinatura digital</li>
            <li>O contratante recebera um link para assinar via DocuSeal</li>
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

      {participacaoWarning && (
        <div className="p-4 rounded-lg bg-amber-50 text-amber-800 border border-amber-200">
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
              {isEdit ? "Salvar Nova Versao" : "Apenas Gerar Contrato"}
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
