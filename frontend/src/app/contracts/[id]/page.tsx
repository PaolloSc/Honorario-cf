"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useAuthStatus } from "@/app/lib/useAuthStatus";
import {
  getContract,
  downloadContract,
  previewContract,
  updateContractStatus,
  sendForSignature,
  sincronizarAssinatura,
  sendEmail,
  rollbackContract,
  listTestemunhas,
  listColaboradores,
  type ColaboradorWizard,
  type ContractDetail,
  type AuditEntry,
  type VersionSummary,
  type Testemunha,
} from "@/app/lib/api";
import SocioEscritorioSelect from "@/components/SocioEscritorioSelect";
import EnvioWhatsApp from "@/components/EnvioWhatsApp";
import { ComboBox } from "@/components/ui/FormField";
import { formatarDataHora } from "@/app/lib/datas";

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  rascunho: { label: "Rascunho", color: "bg-border/35 text-muted" },
  enviado: { label: "Enviado p/ Assinatura", color: "bg-warning/[0.16] text-warning" },
  assinado: { label: "Assinado", color: "bg-primary/[0.16] text-primary-dark" },
  cancelado: { label: "Cancelado", color: "bg-danger/[0.14] text-danger" },
  recusado: { label: "Recusado", color: "bg-danger/[0.14] text-danger" },
};

const ACTION_LABELS: Record<string, string> = {
  criacao: "Contrato criado",
  edicao: "Contrato editado",
  envio_email: "E-mail enviado",
  envio_assinatura: "Enviado p/ assinatura",
  envio_copia_financeiro: "Cópia enviada ao financeiro",
  envio_participacao_assinatura: "Ficha de participação enviada",
  envio_participacao_final: "Ficha enviada ao financeiro (assinado)",
  envio_ficha_participacao: "Ficha de participação enviada",
  mudanca_status: "Status alterado",
  webhook_assinado: "Assinatura concluída",
  sync_assinado: "Assinatura concluída (verificada no DocuSeal)",
  sync_recusado: "Assinatura recusada (verificada no DocuSeal)",
  webhook_recusado: "Assinatura recusada",
};

const ACTION_ICONS: Record<string, string> = {
  criacao: "bg-blue-100 border-blue-300",
  edicao: "bg-blue-100 border-blue-300",
  envio_email: "bg-amber-100 border-amber-300",
  envio_assinatura: "bg-purple-100 border-purple-300",
  envio_copia_financeiro: "bg-teal-100 border-teal-300",
  envio_participacao_assinatura: "bg-teal-100 border-teal-300",
  envio_participacao_final: "bg-teal-100 border-teal-300",
  envio_ficha_participacao: "bg-teal-100 border-teal-300",
  mudanca_status: "bg-border/40 border-muted",
  webhook_assinado: "bg-green-100 border-green-300",
  sync_assinado: "bg-green-100 border-green-300",
  sync_recusado: "bg-red-100 border-red-300",
  webhook_recusado: "bg-red-100 border-red-300",
};

const formatDate = formatarDataHora;

export default function ContractDetailPage() {
  const sessionStatus = useAuthStatus();
  const params = useParams();
  const contractId = params.id as string;

  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notification, setNotification] = useState<{type: "success" | "error"; message: string} | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [sendingSignature, setSendingSignature] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [showSignaturePanel, setShowSignaturePanel] = useState(false);
  // Testemunhas: roster + selecionadas (do roster) + avulsas
  const [roster, setRoster] = useState<Testemunha[]>([]);
  const [selectedTestemunhaIds, setSelectedTestemunhaIds] = useState<number[]>([]);
  const [rosterTestemunhaPick, setRosterTestemunhaPick] = useState("");
  const [extraTestemunhas, setExtraTestemunhas] = useState<Array<{email: string; name: string}>>([]);
  const [newTestemunhaNome, setNewTestemunhaNome] = useState("");
  const [newTestemunhaEmail, setNewTestemunhaEmail] = useState("");
  const [colaboradores, setColaboradores] = useState<ColaboradorWizard[]>([]);
  const [socioEscritorio, setSocioEscritorio] = useState("");
  const [sincronizando, setSincronizando] = useState(false);
  const [pendentes, setPendentes] = useState<
    Array<{ role: string; name: string; email: string; link: string; whatsapp: string }>
  >([]);

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

  // Contrato aguardando assinatura: confere com o DocuSeal ao abrir a pagina.
  // Sem isto o status so' mudava se o webhook chegasse — e quando ele nao esta'
  // configurado, ou a entrega falha, o contrato ficava em "Enviado p/
  // Assinatura" para sempre mesmo com todas as partes tendo assinado.
  useEffect(() => {
    if (sessionStatus !== "authenticated") return;
    if (contract?.status !== "enviado") return;
    let cancelado = false;
    sincronizarAssinatura(contractId)
      .then((r) => {
        if (cancelado) return;
        if (r.alterado) fetchContract();
        else setPendentes(r.pendentes);
      })
      .catch(() => {
        // Silencioso: e' uma conferencia de fundo. A falha nao pode atrapalhar
        // quem so' queria ver o contrato, e o botao manual continua ali.
      });
    return () => {
      cancelado = true;
    };
  }, [sessionStatus, contract?.status, contractId, fetchContract]);

  useEffect(() => {
    if (sessionStatus !== "authenticated" || !showSignaturePanel) return;
    listTestemunhas()
      .then((r) => setRoster(r.testemunhas))
      .catch(() => setRoster([]));
    listColaboradores()
      .then((r) => {
        setColaboradores(r.colaboradores);
        setSocioEscritorio((atual) => atual || contract?.socio_sugerido || "");
      })
      .catch(() => setColaboradores([]));
  }, [sessionStatus, showSignaturePanel, contract?.socio_sugerido]);

  const handlePreview = async () => {
    if (showPreview) {
      setShowPreview(false);
      return;
    }
    setLoadingPreview(true);
    try {
      setPreviewHtml(await previewContract(contractId));
      setShowPreview(true);
    } catch {
      setNotification({type: "error", message: "Erro ao carregar visualização do contrato"});
    } finally {
      setLoadingPreview(false);
    }
  };

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

  const handleSincronizar = async () => {
    setSincronizando(true);
    try {
      const r = await sincronizarAssinatura(contractId);
      if (r.alterado) fetchContract();
      else setPendentes(r.pendentes);
      // O componente de notificacao so' tem sucesso/erro; consultar o DocuSeal e
      // descobrir que nada mudou nao e' erro. O texto do backend ja' diferencia.
      setNotification({ type: "success", message: r.detalhe });
    } catch (e) {
      setNotification({
        type: "error",
        message: e instanceof Error ? e.message : "Erro ao consultar o DocuSeal",
      });
    } finally {
      setSincronizando(false);
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
      setNotification({type: "error", message: "E-mail do contratante não encontrado"});
      return;
    }

    setSendingSignature(true);
    setNotification(null);

    try {
      const signatarios: Array<{email: string; name: string; role: string}> = [
        { email: signerEmail, name: signerName, role: "Contratante" },
      ];

      // Honorários: o sócio escolhido assina pelo escritório. No consumidor o backend
      // injeta a contratada fixa.
      const socio = colaboradores.find((c) => c.email === socioEscritorio);
      if (ehHonorarios && socio) {
        signatarios.push({ email: socio.email, name: socio.name, role: "Contratado" });
      }

      // Testemunhas: do roster (selecionadas) + avulsas. Lilian (Testemunha 1) e injetada no backend.
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
      setNotification({type: "error", message: "E-mail do contratante não encontrado"});
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
        <div className="rounded-lg border border-danger bg-danger/[0.08] p-4 text-sm text-danger">
          {error || "Contrato não encontrado"}
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
  const ehHonorarios = (contract.tipo_contrato ?? "honorarios") === "honorarios";

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
            ID: {contract.contract_id.slice(0, 8)}... | Versão {contract.current_version}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${statusInfo.color}`}>
            {statusInfo.label}
          </span>
        </div>
      </div>

      {notification && (
        <div className={`p-4 rounded-lg mb-4 ${notification.type === "success" ? "bg-primary/[0.1] text-primary-dark border border-primary" : "bg-danger/[0.08] text-danger border border-danger"}`}>
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
          onClick={handlePreview}
          disabled={loadingPreview}
          className="px-5 py-2.5 border border-border text-foreground rounded-lg text-sm font-medium hover:bg-background transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loadingPreview ? "Carregando..." : showPreview ? "Ocultar Visualização" : "Visualizar"}
        </button>
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="px-5 py-2.5 border border-border text-foreground rounded-lg text-sm font-medium hover:bg-background transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {downloading ? "Baixando..." : "Baixar DOCX"}
        </button>
        <button
          onClick={handleResendEmail}
          disabled={sendingEmail}
          className="px-5 py-2.5 border border-warning/40 text-warning rounded-lg text-sm font-medium hover:bg-warning/10 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {sendingEmail ? "Enviando..." : "Reenviar por E-mail"}
        </button>
        {canSendForSignature && (
          <button
            onClick={() => setShowSignaturePanel(!showSignaturePanel)}
            disabled={sendingSignature}
            className="px-5 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sendingSignature ? "Enviando..." : "Enviar para Assinatura"}
          </button>
        )}
        {contract.status === "rascunho" && (
          <button
            onClick={() => handleStatusChange("cancelado")}
            className="px-5 py-2.5 border border-danger/40 text-danger rounded-lg text-sm font-medium hover:bg-danger/10 transition"
          >
            Cancelar
          </button>
        )}
        {contract.status === "enviado" && (
          <>
            <button
              onClick={handleSincronizar}
              disabled={sincronizando}
              className="px-5 py-2.5 border border-accent/40 text-accent rounded-lg text-sm font-medium hover:bg-accent/10 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {sincronizando ? "Consultando..." : "Verificar Assinaturas"}
            </button>
            <button
              onClick={() => handleStatusChange("assinado")}
              className="px-5 py-2.5 border border-primary/40 text-primary-dark rounded-lg text-sm font-medium hover:bg-primary/10 transition"
            >
              Marcar como Assinado
            </button>
          </>
        )}
      </div>

      {contract.status === "enviado" && pendentes.length > 0 && (
        <div className="mb-8 -mt-4 px-4 py-3 bg-warning/10 border border-warning/30 rounded-lg text-sm">
          <p className="font-medium text-warning mb-1">Falta assinar:</p>
          <ul className="space-y-3 text-foreground">
            {pendentes.map((p, i) => (
              <li key={i}>
                {p.name || p.email} <span className="text-muted">({p.role})</span>
                <EnvioWhatsApp nome={p.name || p.email} link={p.link} whatsapp={p.whatsapp} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Inline contract preview */}
      {showPreview && previewHtml && (
        <div className="mb-8 border border-border rounded-xl overflow-hidden bg-white">
          <iframe
            srcDoc={previewHtml}
            title="Pré-visualização do contrato"
            sandbox=""
            className="w-full"
            style={{ height: "70vh" }}
          />
        </div>
      )}

      {/* Signature Panel */}
      {showSignaturePanel && canSendForSignature && (
        <div className="mb-8 p-5 bg-card border border-border rounded-xl">
          <h3 className="text-sm font-semibold text-foreground mb-3">
            Enviar para Assinatura Digital
          </h3>
          <p className="text-xs text-muted mb-3">
            O contratante ({contract.client_email}) é incluído automaticamente.
          </p>

          {ehHonorarios && (
            <SocioEscritorioSelect
              colaboradores={colaboradores}
              value={socioEscritorio}
              onChange={setSocioEscritorio}
            />
          )}

          {/* Testemunhas */}
          <div className="mb-4 pt-3 border-t border-border">
            <p className="text-xs font-semibold text-foreground mb-1">Testemunhas</p>
            <p className="text-xs text-muted mb-2">
              <strong>Testemunha 1 (financeiro)</strong> e incluida automaticamente. Selecione outras do cadastro ou adicione avulsas.
            </p>

            {roster.filter((t) => selectedTestemunhaIds.includes(t.id)).length > 0 && (
              <div className="space-y-1 mb-2">
                {roster
                  .filter((t) => selectedTestemunhaIds.includes(t.id))
                  .map((t) => (
                    <div key={t.id} className="flex items-center gap-2 text-sm bg-card px-3 py-1.5 rounded border border-border">
                      <span className="flex-1">{t.nome} ({t.email})</span>
                      <button
                        onClick={() => setSelectedTestemunhaIds((prev) => prev.filter((id) => id !== t.id))}
                        className="text-danger hover:opacity-80 text-xs font-medium"
                      >
                        Remover
                      </button>
                    </div>
                  ))}
              </div>
            )}

            <div className="flex flex-wrap gap-2 mb-2">
              <div className="flex-1 min-w-48">
                <ComboBox
                  value={rosterTestemunhaPick}
                  onChange={setRosterTestemunhaPick}
                  placeholder="Busque a testemunha por nome ou letra"
                  options={roster
                    .filter((t) => !selectedTestemunhaIds.includes(t.id))
                    .map((t) => ({ value: String(t.id), label: t.nome }))}
                />
              </div>
              <button
                onClick={() => {
                  if (!rosterTestemunhaPick) return;
                  setSelectedTestemunhaIds((prev) => [...prev, Number(rosterTestemunhaPick)]);
                  setRosterTestemunhaPick("");
                }}
                disabled={!rosterTestemunhaPick}
                className="shrink-0 px-3 py-1.5 bg-accent text-white text-sm rounded hover:opacity-90 disabled:opacity-50 transition"
              >
                Adicionar
              </button>
            </div>

            {extraTestemunhas.length > 0 && (
              <div className="space-y-1 mb-2">
                {extraTestemunhas.map((t, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm bg-card px-3 py-1.5 rounded border border-border">
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
                onChange={(e) => setNewTestemunhaNome(e.target.value)}
                placeholder="Nome da testemunha"
                className="flex-1 min-w-40 px-3 py-1.5 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-primary/40"
              />
              <input
                type="email"
                value={newTestemunhaEmail}
                onChange={(e) => setNewTestemunhaEmail(e.target.value)}
                placeholder="email@exemplo.com"
                className="flex-1 min-w-48 px-3 py-1.5 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-primary/40"
              />
              <button
                onClick={() => {
                  if (!newTestemunhaEmail.trim()) return;
                  setExtraTestemunhas((prev) => [...prev, { email: newTestemunhaEmail.trim(), name: newTestemunhaNome.trim() || newTestemunhaEmail.trim() }]);
                  setNewTestemunhaEmail("");
                  setNewTestemunhaNome("");
                }}
                disabled={!newTestemunhaEmail.trim()}
                className="shrink-0 px-3 py-1.5 bg-accent text-white text-sm rounded hover:opacity-90 disabled:opacity-50 transition"
              >
                Adicionar
              </button>
            </div>
          </div>

          {/* Send button */}
          <div className="flex gap-3">
            <button
              onClick={handleSendForSignature}
              disabled={sendingSignature || (ehHonorarios && !socioEscritorio)}
              className="px-5 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark disabled:opacity-50 transition"
            >
              {sendingSignature ? "Enviando..." : "Confirmar e Enviar"}
            </button>
            <button
              onClick={() => setShowSignaturePanel(false)}
              className="px-5 py-2 border border-border text-foreground rounded-lg text-sm hover:bg-background transition"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

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

              let badgeColor = "bg-warning/[0.16] text-warning";
              let badgeLabel = "Aguardando assinatura";
              if (isSuccess) {
                badgeColor = "bg-primary/[0.16] text-primary-dark";
                badgeLabel = "Assinado";
              } else if (isError) {
                badgeColor = "bg-danger/[0.14] text-danger";
                badgeLabel = "Recusado";
              } else if (isSent) {
                badgeColor = "bg-warning/[0.16] text-warning";
                badgeLabel = "Enviado - Aguardando";
              }

              return (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-background border border-border/50">
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
          <h3 className="font-display text-sm font-semibold text-primary-dark mb-3">Informações</h3>
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
                    ? "bg-primary/5 border border-primary"
                    : "bg-background"
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
          Histórico de Ações
        </h3>
        <div className="relative">
          <div className="absolute left-4 top-0 bottom-0 w-px bg-border" />
          <div className="space-y-4">
            {contract.audit_log.map((entry: AuditEntry, i: number) => {
              const iconClass = ACTION_ICONS[entry.action] || "bg-border/40 border-muted";
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
              <p className="text-sm text-muted pl-10">Nenhuma ação registrada.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
