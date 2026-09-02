"use client";

import {
  generateContratoConsumidor,
  listTestemunhas,
  previewContract,
  previewContratoConsumidor,
  sendEmail,
  sendForSignature,
  updateContract,
  type Testemunha,
} from "@/app/lib/api";
import {
  emailContato,
  nomeExibicao,
  nomeSignatario,
  type ConsumidorFormData,
} from "@/types/consumidor";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

interface Props {
  data: ConsumidorFormData;
  editContractId?: string;
  onSaveComplete?: (contractId: string) => void;
}

type Status = "idle" | "generating" | "sending" | "sent_email" | "success" | "error";

export default function StepEnvio({ data, editContractId, onSaveComplete }: Props) {
  const router = useRouter();
  const isEdit = !!editContractId;

  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [contractId, setContractId] = useState<string | null>(editContractId || null);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [previewErro, setPreviewErro] = useState("");
  const [emailWarning, setEmailWarning] = useState("");
  const [signatureSent, setSignatureSent] = useState(false);
  const [recipients, setRecipients] = useState(() =>
    data.contratantes.map((c) => ({ email: emailContato(c), nome: nomeExibicao(c) }))
  );
  const [roster, setRoster] = useState<Testemunha[]>([]);
  const [testemunhasSelecionadas, setTestemunhasSelecionadas] = useState<number[]>([]);

  useEffect(() => {
    listTestemunhas()
      .then((r) => setRoster(r.testemunhas))
      .catch(() => setRoster([]));
  }, []);

  // Antes de gerar, a prévia vem do formulário (sem gravar nada); depois de gerar,
  // passa a vir do contrato salvo, que já reflete a versão em disco.
  useEffect(() => {
    if (status === "generating" || status === "sending") return;

    if (contractId) {
      previewContract(contractId).then(setPreviewHtml).catch(() => setPreviewHtml(null));
      return;
    }

    const controller = new AbortController();
    // Debounce: cada prévia gera um DOCX no servidor, não dá para fazer por tecla.
    const timer = setTimeout(() => {
      previewContratoConsumidor(data, controller.signal)
        .then((html) => {
          setPreviewHtml(html);
          setPreviewErro("");
        })
        .catch((e) => {
          if (e instanceof Error && e.name === "AbortError") return;
          setPreviewHtml(null);
          setPreviewErro("Não foi possível montar a prévia agora.");
        });
    }, 500);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [contractId, status, data]);

  const salvar = async (): Promise<string> => {
    if (isEdit) {
      const r = await updateContract(editContractId, data as unknown as Record<string, unknown>);
      if (!r.success) throw new Error(r.message || "Erro ao salvar contrato");
      return r.contract_id;
    }
    const r = await generateContratoConsumidor(data);
    if (!r.success) throw new Error(r.message || "Erro ao gerar contrato");
    return r.contract_id!;
  };

  const handleSalvarSomente = async () => {
    setIsSubmitting(true);
    setStatus("generating");
    setMessage(isEdit ? "Salvando nova versão..." : "Gerando contrato...");
    try {
      const id = await salvar();
      setContractId(id);
      setStatus("sent_email");
      setMessage(
        isEdit
          ? "Nova versão salva. Você pode enviar para assinatura ou voltar para a lista."
          : "Contrato gerado. Você pode enviar para assinatura ou voltar para a lista."
      );
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Erro desconhecido");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGerarEEnviar = async () => {
    setIsSubmitting(true);
    setStatus("generating");
    setMessage(isEdit ? "Salvando nova versão..." : "Gerando contrato...");
    try {
      const id = await salvar();
      setContractId(id);

      setStatus("sending");
      setMessage("Enviando e-mail...");

      const destinatarios = recipients.filter((r) => r.email.trim());
      if (destinatarios.length === 0) {
        throw new Error("Nenhum e-mail de destinatário informado.");
      }

      const falhas: string[] = [];
      for (const dest of destinatarios) {
        try {
          const r = await sendEmail({
            contract_id: id,
            destinatario_email: dest.email.trim(),
            destinatario_nome: dest.nome || dest.email,
            assunto: "Contrato de Prestação de Serviços Advocatícios - C&F Advogados - Para Conferência",
          });
          if (!r.success) falhas.push(`${dest.email}: ${r.message || "erro"}`);
        } catch (err) {
          falhas.push(`${dest.email}: ${err instanceof Error ? err.message : "erro"}`);
        }
      }

      if (falhas.length === destinatarios.length) {
        throw new Error(`Erro ao enviar e-mail: ${falhas.join("; ")}`);
      }
      if (falhas.length > 0) {
        setEmailWarning(`Alguns e-mails não foram enviados: ${falhas.join("; ")}`);
      }

      setStatus("sent_email");
      setMessage(
        "Contrato gerado e enviado por e-mail. Agora você pode enviar para assinatura digital."
      );
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Erro desconhecido");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAssinatura = async () => {
    if (!contractId) return;
    setIsSubmitting(true);
    setStatus("sending");
    setMessage("Enviando para assinatura digital...");
    try {
      // Na PJ quem assina é o representante legal.
      const signatarios = data.contratantes
        .filter((c) => emailContato(c))
        .map((c) => ({
          email: emailContato(c),
          name: nomeSignatario(c),
          role: "Contratante",
        }));

      if (signatarios.length === 0) {
        throw new Error("Informe o e-mail de pelo menos um contratante para assinar.");
      }

      for (const t of roster.filter((r) => testemunhasSelecionadas.includes(r.id))) {
        signatarios.push({ email: t.email, name: t.nome, role: "Testemunha" });
      }

      const r = await sendForSignature({ contract_id: contractId, signatarios });
      if (!r.success) throw new Error(r.message || "Erro ao enviar para assinatura");

      setSignatureSent(true);
      setStatus("success");
      setMessage("Documento enviado para assinatura digital com sucesso!");
      if (onSaveComplete) setTimeout(() => onSaveComplete(contractId), 2000);
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "Erro desconhecido");
    } finally {
      setIsSubmitting(false);
    }
  };

  const podeAssinar = status === "sent_email" || status === "success";

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">
        {isEdit ? "Salvar Nova Versão" : "Revisão e Envio"}
      </h2>

      <div className="bg-primary/[0.08] border border-primary rounded-lg p-4">
        <h3 className="font-medium text-primary-dark mb-2">Resumo</h3>
        <div className="text-sm text-primary-dark space-y-1">
          <p>
            <strong>Contratante(s):</strong>{" "}
            {data.contratantes.map(nomeExibicao).filter(Boolean).join(", ") || "—"}
          </p>
          <p>
            <strong>Ré(s):</strong>{" "}
            {data.res.map((re) => re.razao_social || re.companhia).filter(Boolean).join("; ") ||
              "—"}
          </p>
          <p>
            <strong>Honorário:</strong> 25% do êxito · milheiro de{" "}
            {data.res.map((re) => re.companhia).filter(Boolean).join(", ") || "—"}
          </p>
          <p className="pt-2">
            <strong>E-mail(s) para envio:</strong>
          </p>
          <div className="space-y-2 mt-1">
            {recipients.map((r, i) => (
              <div key={i}>
                <label className="block text-xs text-primary-dark mb-0.5">
                  {r.nome || `Contratante ${i + 1}`}
                </label>
                <input
                  type="email"
                  value={r.email}
                  onChange={(e) =>
                    setRecipients((prev) =>
                      prev.map((x, idx) => (idx === i ? { ...x, email: e.target.value } : x))
                    )
                  }
                  disabled={podeAssinar}
                  className="w-full px-3 py-2 border border-border bg-card text-foreground rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:bg-border/35 disabled:border-muted"
                  placeholder="email@exemplo.com"
                />
              </div>
            ))}
          </div>
        </div>
      </div>

      {previewErro && !previewHtml && (
        <p className="text-sm text-warning bg-warning/[0.08] border border-warning rounded-lg px-3 py-2">
          {previewErro}
        </p>
      )}

      {previewHtml && (
        <div>
          <h3 className="font-medium mb-2">
            {contractId
              ? "Prévia do contrato (como ficará no Word/PDF)"
              : "Prévia do contrato (ainda não foi gerado nem salvo)"}
          </h3>
          <div className="border border-border rounded-xl overflow-hidden bg-white">
            <iframe
              srcDoc={previewHtml}
              title="Prévia do contrato"
              sandbox=""
              className="w-full"
              style={{ height: "60vh" }}
            />
          </div>
        </div>
      )}

      {message && (
        <div
          className={`p-4 rounded-lg text-sm ${
            status === "error"
              ? "bg-danger/[0.08] text-danger border border-danger"
              : status === "success" || status === "sent_email"
              ? "bg-primary/[0.08] text-primary-dark border border-primary"
              : "bg-primary/[0.08] text-primary-dark border border-primary"
          }`}
        >
          {message}
        </div>
      )}

      {emailWarning && (
        <div className="p-4 rounded-lg text-sm bg-warning/[0.08] text-warning border border-warning">
          {emailWarning}
        </div>
      )}

      {podeAssinar && !signatureSent && roster.length > 0 && (
        <div className="border border-border rounded-xl p-5">
          <h3 className="font-medium mb-3">Testemunhas para assinatura digital</h3>
          <div className="space-y-2">
            {roster.map((t) => (
              <label key={t.id} className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={testemunhasSelecionadas.includes(t.id)}
                  onChange={(e) =>
                    setTestemunhasSelecionadas((prev) =>
                      e.target.checked ? [...prev, t.id] : prev.filter((id) => id !== t.id)
                    )
                  }
                  className="h-4 w-4 rounded border-border text-primary"
                />
                {t.nome} <span className="text-muted">({t.email})</span>
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        {!podeAssinar && (
          <>
            <button
              type="button"
              onClick={handleGerarEEnviar}
              disabled={isSubmitting}
              className="px-6 py-2.5 bg-primary text-white rounded-lg font-medium hover:bg-primary-dark transition disabled:opacity-40"
            >
              {isEdit ? "Salvar e enviar por e-mail" : "Gerar e enviar por e-mail"}
            </button>
            <button
              type="button"
              onClick={handleSalvarSomente}
              disabled={isSubmitting}
              className="px-6 py-2.5 border border-border rounded-lg font-medium hover:bg-background transition disabled:opacity-40"
            >
              {isEdit ? "Salvar sem enviar" : "Gerar sem enviar"}
            </button>
          </>
        )}

        {podeAssinar && !signatureSent && (
          <button
            type="button"
            onClick={handleAssinatura}
            disabled={isSubmitting}
            className="px-6 py-2.5 bg-primary text-white rounded-lg font-medium hover:bg-primary-dark transition disabled:opacity-40"
          >
            Enviar para assinatura digital
          </button>
        )}

        {contractId && (
          <button
            type="button"
            onClick={() =>
              onSaveComplete ? onSaveComplete(contractId) : router.push(`/contracts/${contractId}`)
            }
            className="px-6 py-2.5 border border-border rounded-lg font-medium hover:bg-background transition"
          >
            Ir para o contrato
          </button>
        )}
      </div>
    </div>
  );
}
