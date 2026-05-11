"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
  getContract,
  downloadContract,
  updateContractStatus,
  sendForSignature,
  sendEmail,
  rollbackContract,
  type ContractDetail,
  type AuditEntry,
  type VersionSummary,
} from "@/app/lib/api";

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  rascunho: { label: "Rascunho", color: "bg-gray-100 text-gray-700" },
  enviado: { label: "Enviado p/ Assinatura", color: "bg-amber-100 text-amber-800" },
  assinado: { label: "Assinado", color: "bg-green-100 text-green-800" },
  cancelado: { label: "Cancelado", color: "bg-red-100 text-red-800" },
  recusado: { label: "Recusado", color: "bg-red-100 text-red-800" },
};

const ACTION_LABELS: Record<string, string> = {
  criacao: "Contrato criado",
  edicao: "Contrato editado",
  envio_email: "E-mail enviado",
  envio_assinatura: "Enviado p/ assinatura",
  envio_copia_financeiro: "Copia enviada ao financeiro",
  envio_participacao_assinatura: "Ficha de participacao enviada",
  envio_ficha_participacao: "Ficha de participacao enviada",
  mudanca_status: "Status alterado",
  webhook_assinado: "Assinatura concluida",
  webhook_recusado: "Assinatura recusada",
};

const ACTION_ICONS: Record<string, string> = {
  criacao: "bg-blue-100 border-blue-300",
  edicao: "bg-blue-100 border-blue-300",
  envio_email: "bg-amber-100 border-amber-300",
  envio_assinatura: "bg-purple-100 border-purple-300",
  envio_copia_financeiro: "bg-teal-100 border-teal-300",
  envio_participacao_assinatura: "bg-teal-100 border-teal-300",
  envio_ficha_participacao: "bg-teal-100 border-teal-300",
  mudanca_status: "bg-gray-100 border-gray-300",
  webhook_assinado: "bg-green-100 border-green-300",
  webhook_recusado: "bg-red-100 border-red-300",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ContractDetailPage() {
  const { status: sessionStatus } = useSession();
  const params = useParams();
  const contractId = params.id as string;

  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notification, setNotification] = useState<{type: "success" | "error"; message: string} | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [sendingSignature, setSendingSignature] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);

  const fetchContract = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getContract(contractId);
      setContract(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar contrato");
    } finally {
      setLoading(false);
    }
  }, [contractId]);

  useEffect(() => {
    if (sessionStatus === "authenticated") {
      fetchContract();
    }
  }, [fetchContract, sessionStatus]);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const blob = await downloadContract(contractId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `contrato_${contractId}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setNotification({type: "error", message: "Erro ao baixar contrato"});
    } finally {
      setDownloading(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!window.confirm(`Tem certeza que deseja alterar o status para "${newStatus}"?`)) return;
    try {
      await updateContractStatus(contractId, newStatus);
      fetchContract();
      setNotification({type: "success", message: "Status alterado com sucesso"});
    } catch {
      setNotification({type: "error", message: "Erro ao alterar status"});
    }
  };

  const handleSendForSignature = async () => {
    if (!contract) return;

    const signerEmail = contract.client_email;
    const signerName = contract.client_name;

    if (!signerEmail) {
      setNotification({type: "error", message: "E-mail do contratante nao encontrado"});
      return;
    }

    if (!window.confirm(`Enviar contrato para assinatura digital de ${signerName} (${signerEmail})?`)) return;

    setSendingSignature(true);
    setNotification(null);

    try {
      const result = await sendForSignature({
        contract_id: contractId,
        signatarios: [{ email: signerEmail, name: signerName, role: "Contratante" }],
      });

      if (!result.success) {
        throw new Error(result.message || "Erro ao enviar para assinatura");
      }

      setNotification({type: "success", message: "Documento enviado para assinatura digital com sucesso!"});
      fetchContract(); // Refresh to update status and audit log
    } catch (e) {
      setNotification({type: "error", message: e instanceof Error ? e.message : "Erro ao enviar para assinatura"});
    } finally {
      setSendingSignature(false);
    }
  };

  const handleResendEmail = async () => {
    if (!contract) return;

    const recipientEmail = contract.client_email;
    const recipientName = contract.client_name;

    if (!recipientEmail) {
      setNotification({type: "error", message: "E-mail do contratante nao encontrado"});
      return;
    }

    if (!window.confirm(`Reenviar contrato por e-mail para ${recipientName} (${recipientEmail})?`)) return;

    setSendingEmail(true);
    setNotification(null);

    try {
      const result = await sendEmail({
        contract_id: contractId,
        destinatario_email: recipientEmail,
        destinatario_nome: recipientName,
        assunto: "Contrato de Honorários - C&F Advogados - Para Conferência",
      });

      if (!result.success) {
        throw new Error(result.message || "Erro ao enviar e-mail");
      }

      setNotification({type: "success", message: "E-mail reenviado com sucesso!"});
      fetchContract();
    } catch (e) {
      setNotification({type: "error", message: e instanceof Error ? e.message : "Erro ao reenviar e-mail"});
    } finally {
      setSendingEmail(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center text-muted">
        Carregando contrato...
      </div>
    );
  }

  if (error || !contract) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {error || "Contrato nao encontrado"}
        </div>
        <a href="/contracts" className="mt-4 inline-block text-sm text-primary hover:underline">
          Voltar para lista
        </a>
      </div>
    );
  }

  const statusInfo = STATUS_LABELS[contract.status] || STATUS_LABELS.rascunho;

  // Determine signature-related info from audit log
  const signatureEntries = contract.audit_log.filter(
    (e) => e.action === "envio_assinatura" || e.action === "webhook_assinado" || e.action === "webhook_recusado"
  );
  const lastSignatureEntry = signatureEntries.length > 0 ? signatureEntries[0] : null;
  const canSendForSignature = contract.status === "rascunho" || contract.status === "enviado";

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <a href="/contracts" className="text-sm text-muted hover:text-foreground transition mb-2 inline-block">
            &larr; Voltar
          </a>
          <h1 className="font-display text-xl font-semibold text-primary-dark tracking-wide">
            {contract.client_name || "Contrato"}
          </h1>
          <p className="text-sm text-muted mt-1">
            ID: {contract.contract_id.slice(0, 8)}... | Versao {contract.current_version}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${statusInfo.color}`}>
            {statusInfo.label}
          </span>
        </div>
      </div>

      {notification && (
        <div className={`p-4 rounded-lg mb-4 ${notification.type === "success" ? "bg-green-50 text-green-800 border border-green-200" : "bg-red-50 text-red-800 border border-red-200"}`}>
          <div className="flex justify-between items-center">
            <span>{notification.message}</span>
            <button onClick={() => setNotification(null)} className="text-sm underline">Fechar</button>
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-3 mb-8">
        <a
          href={`/contracts/${contractId}/edit`}
          className="px-5 py-2.5 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark transition"
        >
          Editar Contrato
        </a>
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="px-5 py-2.5 border border-border text-foreground rounded-lg text-sm font-medium hover:bg-gray-50 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {downloading ? "Baixando..." : "Baixar DOCX"}
        </button>
        <button
          onClick={handleResendEmail}
          disabled={sendingEmail}
          className="px-5 py-2.5 border border-amber-200 text-amber-700 rounded-lg text-sm font-medium hover:bg-amber-50 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {sendingEmail ? "Enviando..." : "Reenviar por E-mail"}
        </button>
        {canSendForSignature && (
          <button
            onClick={handleSendForSignature}
            disabled={sendingSignature}
            className="px-5 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sendingSignature ? "Enviando..." : "Enviar para Assinatura"}
          </button>
        )}
        {contract.status === "rascunho" && (
          <button
            onClick={() => handleStatusChange("cancelado")}
            className="px-5 py-2.5 border border-red-200 text-red-700 rounded-lg text-sm font-medium hover:bg-red-50 transition"
          >
            Cancelar
          </button>
        )}
        {contract.status === "enviado" && (
          <button
            onClick={() => handleStatusChange("assinado")}
            className="px-5 py-2.5 border border-green-200 text-green-700 rounded-lg text-sm font-medium hover:bg-green-50 transition"
          >
            Marcar como Assinado
          </button>
        )}
      </div>

      {/* Signature Status Card */}
      {signatureEntries.length > 0 && (
        <div className="bg-card rounded-xl border border-border p-5 mb-8">
          <h3 className="font-display text-sm font-semibold text-primary-dark mb-3">
            Status da Assinatura Digital
          </h3>
          <div className="space-y-3">
            {signatureEntries.map((entry, i) => {
              const isSuccess = entry.action === "webhook_assinado";
              const isError = entry.action === "webhook_recusado";
              const isSent = entry.action === "envio_assinatura";

              let badgeColor = "bg-amber-100 text-amber-800";
              let badgeLabel = "Aguardando assinatura";
              if (isSuccess) {
                badgeColor = "bg-green-100 text-green-800";
                badgeLabel = "Assinado";
              } else if (isError) {
                badgeColor = "bg-red-100 text-red-800";
                badgeLabel = "Recusado";
              } else if (isSent) {
                badgeColor = "bg-amber-100 text-amber-800";
                badgeLabel = "Enviado - Aguardando";
              }

              return (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-border/50">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${badgeColor}`}>
                        {badgeLabel}
                      </span>
                      {entry.user_email && (
                        <span className="text-xs text-muted">por {entry.user_email}</span>
                      )}
                    </div>
                    {entry.detail && (
                      <p className="text-xs text-muted mt-1">{entry.detail}</p>
                    )}
                  </div>
                  <span className="text-xs text-muted whitespace-nowrap ml-4">
                    {formatDate(entry.created_at)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-card rounded-xl border border-border p-5">
          <h3 className="font-display text-sm font-semibold text-primary-dark mb-3">Informacoes</h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted">Cliente</dt>
              <dd className="font-medium">{contract.client_name || "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">E-mail</dt>
              <dd>{contract.client_email || "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">Criado por</dt>
              <dd>{contract.created_by || "—"}</dd>
            </div>
            {contract.updated_by && contract.updated_by !== contract.created_by && (
              <div className="flex justify-between">
                <dt className="text-muted">Editado por</dt>
                <dd>{contract.updated_by}</dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt className="text-muted">Criado em</dt>
              <dd>{formatDate(contract.created_at)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">Atualizado em</dt>
              <dd>{formatDate(contract.updated_at)}</dd>
            </div>
          </dl>
        </div>

        {/* Versions */}
        <div className="bg-card rounded-xl border border-border p-5">
          <h3 className="font-display text-sm font-semibold text-primary-dark mb-3">
            Versoes ({contract.versions.length})
          </h3>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {contract.versions.map((v: VersionSummary) => (
              <div
                key={v.version_number}
                className={`flex items-center justify-between text-sm px-3 py-2 rounded-lg ${
                  v.version_number === contract.current_version
                    ? "bg-primary/5 border border-primary/20"
                    : "bg-gray-50"
                }`}
              >
                <div>
                  <span className="font-medium">v{v.version_number}</span>
                  {v.version_number === contract.current_version && (
                    <span className="ml-2 text-xs text-primary font-medium">atual</span>
                  )}
                  {v.docuseal_submission_id && (
                    <span className="ml-2 text-xs text-accent font-medium">DocuSeal #{v.docuseal_submission_id}</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {v.version_number !== contract.current_version && (
                    <button
                      onClick={async () => {
                        if (!window.confirm(`Reverter contrato para a versao ${v.version_number}?`)) return;
                        try {
                          const result = await rollbackContract(contractId, v.version_number);
                          if (result.success) {
                            setNotification({type: "success", message: result.message});
                            fetchContract();
                          }
                        } catch (e) {
                          setNotification({type: "error", message: e instanceof Error ? e.message : "Erro ao reverter"});
                        }
                      }}
                      className="px-2 py-0.5 text-xs text-primary border border-primary/30 rounded hover:bg-primary/5 transition"
                    >
                      Restaurar
                    </button>
                  )}
                  <span className="text-xs text-muted">{formatDate(v.created_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Audit Log */}
      <div className="bg-card rounded-xl border border-border p-5">
        <h3 className="font-display text-sm font-semibold text-primary-dark mb-4">
          Historico de Acoes
        </h3>
        <div className="relative">
          <div className="absolute left-4 top-0 bottom-0 w-px bg-border" />
          <div className="space-y-4">
            {contract.audit_log.map((entry: AuditEntry, i: number) => {
              const iconClass = ACTION_ICONS[entry.action] || "bg-gray-100 border-gray-300";
              return (
                <div key={i} className="relative pl-10">
                  <div className={`absolute left-2.5 top-1.5 w-3 h-3 rounded-full border-2 ${iconClass}`} />
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {ACTION_LABELS[entry.action] || entry.action}
                      {entry.version_number && (
                        <span className="text-xs text-muted ml-2">v{entry.version_number}</span>
                      )}
                      {entry.user_email && (
                        <span className="text-xs text-primary/70 ml-2">por {entry.user_email}</span>
                      )}
                    </p>
                    {entry.detail && <p className="text-xs text-muted mt-0.5">{entry.detail}</p>}
                    <p className="text-xs text-muted/60 mt-0.5">{formatDate(entry.created_at)}</p>
                  </div>
                </div>
              );
            })}
            {contract.audit_log.length === 0 && (
              <p className="text-sm text-muted pl-10">Nenhuma acao registrada.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
