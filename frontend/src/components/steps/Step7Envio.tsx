"use client";

import { useState } from "react";
import type { Contratante, ContratantePF, ContratantePJ, ContratoFormData } from "@/types/contract";
import { generateContract, sendEmail, sendForSignature } from "@/app/lib/api";

interface Step7EnvioProps {
  data: ContratoFormData;
}

function getContratanteNome(c: Contratante): string {
  if (c.tipo === "PF") return (c as ContratantePF).nome;
  return (c as ContratantePJ).razao_social;
}

export default function Step7Envio({ data }: Step7EnvioProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [status, setStatus] = useState<"idle" | "generating" | "sending" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [contractId, setContractId] = useState<string | null>(null);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setStatus("generating");
    setMessage("Gerando contrato...");

    try {
      const result = await generateContract(data);

      if (!result.success) {
        throw new Error(result.message || "Erro ao gerar contrato");
      }

      setContractId(result.contract_id!);
      setStatus("sending");
      setMessage("Enviando e-mail...");

      const emailResult = await sendEmail({
        contract_id: result.contract_id!,
        destinatario_email: data.email_destinatario || data.contratantes[0].email,
        destinatario_nome: getContratanteNome(data.contratantes[0]),
        assunto: "Contrato de Honorários - C&F Advogados - Para Conferência",
      });

      if (!emailResult.success) {
        throw new Error(emailResult.message || "Erro ao enviar e-mail");
      }

      setStatus("success");
      setMessage("Contrato gerado e enviado por e-mail com sucesso!");
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

      setStatus("success");
      setMessage("Documento enviado para assinatura digital com sucesso!");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Erro desconhecido");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Revisão e Envio</h2>

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
            <strong>E-mail para envio:</strong>{" "}
            {data.email_destinatario || data.contratantes[0].email}
          </p>
        </div>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <h3 className="font-medium text-amber-900 mb-2">Próximos passos</h3>
        <ol className="text-sm text-amber-800 space-y-1 list-decimal list-inside">
          <li>O contrato será gerado e enviado por e-mail para conferência</li>
          <li>Após confirmação, você poderá enviar para assinatura digital</li>
          <li>O contratante receberá um link para assinar via DocuSeal</li>
        </ol>
      </div>

      {message && (
        <div
          className={`p-4 rounded-lg ${
            status === "success"
              ? "bg-green-50 text-green-800 border border-green-200"
              : status === "error"
              ? "bg-red-50 text-red-800 border border-red-200"
              : "bg-blue-50 text-blue-800 border border-blue-200"
          }`}
        >
          {message}
        </div>
      )}

      <div className="flex gap-4 flex-wrap">
        <button
          onClick={handleSubmit}
          disabled={isSubmitting || status === "success"}
          className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-50 transition"
        >
          {isSubmitting && status === "generating"
            ? "Gerando contrato..."
            : isSubmitting && status === "sending"
            ? "Enviando..."
            : "Gerar e Enviar por E-mail"}
        </button>

        {contractId && status === "success" && (
          <button
            onClick={handleSendForSignature}
            disabled={isSubmitting}
            className="px-4 py-2 bg-accent text-white rounded-lg hover:opacity-90 disabled:opacity-50 transition"
          >
            Enviar para Assinatura Digital
          </button>
        )}
      </div>
    </div>
  );
}
