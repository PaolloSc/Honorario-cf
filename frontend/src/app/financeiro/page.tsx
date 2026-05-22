"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import {
  Participacao,
  RegrasParticipacao,
  ResumoParticipacao,
  aprovarParticipacao,
  atualizarStatusPagamento,
  createParticipacao,
  encerrarVinculo,
  getAuthHeaders,
  getRegrasParticipacao,
  getResumoParticipacao,
  listContratosPendentes,
  listParticipacoes,
  registrarPagamento,
  simularParticipacao,
  type ContratoPendente,
  type PagamentoStatus,
} from "@/app/lib/api";
import { HealthBanner } from "@/components/nfse/HealthBanner";
import { NotasFiscaisLista } from "@/components/nfse/NotasFiscaisLista";
import { SyncButton } from "@/components/nfse/SyncButton";

const TIPOS_HONORARIO = [
  { value: "hora", label: "Hora trabalhada (limite 3 anos)" },
  { value: "partido", label: "Partido (limite 2 anos)" },
  { value: "mensalidade", label: "Mensalidade (limite 2 anos)" },
  { value: "exito", label: "Êxito (sem limite)" },
  { value: "prolabore", label: "Prolabore (sem limite)" },
  { value: "misto", label: "Misto (aplica regra de cada subtipo)" },
];

function brl(n: number) {
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const STATUS_LABELS: Record<PagamentoStatus, string> = {
  a_receber: "A receber",
  aguardando_pagamento: "Aguardando pagamento",
  pago: "Pago",
};

function rowBgByStatus(s: PagamentoStatus): string {
  // Cores da planilha: A receber=amarelo, Aguardando=laranja, Pago=azul
  if (s === "a_receber") return "bg-yellow-50";
  if (s === "aguardando_pagamento") return "bg-orange-50";
  if (s === "pago") return "bg-blue-50";
  return "";
}

function StatusSelect({
  value,
  onChange,
}: {
  value: PagamentoStatus;
  onChange: (next: PagamentoStatus) => void | Promise<void>;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as PagamentoStatus)}
      className="text-xs border border-border rounded px-1 py-0.5 bg-white"
    >
      <option value="a_receber">{STATUS_LABELS.a_receber}</option>
      <option value="aguardando_pagamento">{STATUS_LABELS.aguardando_pagamento}</option>
      <option value="pago">{STATUS_LABELS.pago}</option>
    </select>
  );
}

export default function FinanceiroPage() {
  const { data: session, status } = useSession();
  const [role, setRole] = useState<string | null>(null);
  const [accessDenied, setAccessDenied] = useState(false);
  const [regras, setRegras] = useState<RegrasParticipacao | null>(null);
  const [items, setItems] = useState<Participacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"pendentes" | "lista" | "nova" | "simular" | "nfse">("pendentes");
  const [pendentes, setPendentes] = useState<ContratoPendente[]>([]);

  const token = session?.accessToken;
  const devMode = typeof window !== "undefined" && process.env.NEXT_PUBLIC_DEV_MODE === "true";
  const hasDevSession = typeof window !== "undefined" && !!localStorage.getItem("dev_user_email");

  // 1) Verifica perfil
  useEffect(() => {
    if (!token && !(devMode && hasDevSession)) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
      (typeof window !== "undefined" ? `${window.location.protocol}//${window.location.hostname}` : "");
    fetch(`${apiBase}/api/users/me`, { headers: getAuthHeaders() })
      .then((r) => {
        if (r.status === 401) {
          window.location.href = "/financeiro/login";
          return null;
        }
        return r.json();
      })
      .then((u) => {
        if (!u) return;
        setRole(u.role);
        if (u.role !== "financeiro" && u.role !== "admin") setAccessDenied(true);
      })
      .catch(() => setError("Falha ao verificar perfil"));
  }, [token, devMode, hasDevSession]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [r, l, p] = await Promise.all([
        getRegrasParticipacao(),
        listParticipacoes(),
        listContratosPendentes(true),
      ]);
      setRegras(r);
      setItems(l.participacoes);
      setPendentes(p.contratos);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (role === "financeiro" || role === "admin") refresh();
  }, [role, refresh]);

  if (status === "loading") {
    return <div className="p-8 text-muted">Carregando sessão...</div>;
  }

  if (accessDenied) {
    return (
      <div className="max-w-xl mx-auto mt-16 p-8 bg-red-50 border border-red-200 rounded-lg text-center">
        <h2 className="text-lg font-semibold text-red-900 mb-2">Acesso Restrito</h2>
        <p className="text-red-700">
          Esta página é exclusiva do setor financeiro. Solicite ao administrador o perfil "financeiro".
        </p>
        <a href="/" className="mt-4 inline-block text-sm text-primary hover:underline">
          Voltar
        </a>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-primary-dark tracking-wide">
          Setor Financeiro — Participações
        </h1>
        <p className="text-sm text-muted mt-1">
          Cálculo e gestão de participações em honorários contratuais conforme regras vigentes a partir de
          {regras ? ` ${regras.vigencia_inicio}` : ""}.
        </p>
      </header>

      {regras && <RegrasBox regras={regras} />}

      <nav className="flex gap-2 mt-6 mb-4 border-b border-border">
        {(["pendentes", "lista", "nova", "simular", "nfse"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
              tab === t
                ? "border-primary-dark text-primary-dark"
                : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {t === "pendentes" && `Pendentes (${pendentes.length})`}
            {t === "lista" && `Participações (${items.length})`}
            {t === "nova" && "Nova Participação"}
            {t === "simular" && "Simulador"}
            {t === "nfse" && "Notas Fiscais"}
          </button>
        ))}
      </nav>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {tab === "pendentes" && (
        <PendentesLista pendentes={pendentes} loading={loading} onRefresh={refresh} />
      )}
      {tab === "lista" && (
        <ListaParticipacoes items={items} loading={loading} onRefresh={refresh} />
      )}
      {tab === "nova" && <FormNovaParticipacao onCreated={refresh} setTab={setTab} />}
      {tab === "simular" && <Simulador />}
      {tab === "nfse" && <AbaNotasFiscais />}
    </div>
  );
}

function AbaNotasFiscais() {
  const now = new Date();
  const defaultMes = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [mes, setMes] = useState(defaultMes);
  const [cnpj, setCnpj] = useState("");

  return (
    <div className="space-y-4">
      <HealthBanner />
      <div className="flex items-end gap-3">
        <label className="block text-xs">
          <span className="block text-muted mb-1">Competência</span>
          <input
            type="month"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            className="px-2 py-1 border border-border rounded"
          />
        </label>
        <label className="block text-xs">
          <span className="block text-muted mb-1">CNPJ prestador</span>
          <input
            value={cnpj}
            onChange={(e) => setCnpj(e.target.value)}
            placeholder="só dígitos"
            className="px-2 py-1 border border-border rounded font-mono"
          />
        </label>
        <SyncButton cnpj={cnpj} />
      </div>
      <NotasFiscaisLista competencia_mes={mes} />
    </div>
  );
}

function RegrasBox({ regras }: { regras: RegrasParticipacao }) {
  return (
    <details className="bg-card border border-border rounded-lg p-4 text-sm">
      <summary className="cursor-pointer font-medium text-foreground">
        Regras vigentes (clique para expandir)
      </summary>
      <div className="mt-3 grid md:grid-cols-2 gap-3 text-muted">
        <p><strong className="text-foreground">Vigência:</strong> {regras.vigencia_inicio} (sem retroatividade para valores anteriores a 31/07/2024)</p>
        <p><strong className="text-foreground">Limites:</strong> Captação ≤ {regras.limite_captacao_pct}%, Performance ≤ {regras.limite_performance_pct}%, Combo ≤ {regras.limite_combo_pct}%</p>
        <p><strong className="text-foreground">Aplica-se a:</strong> {regras.honorarios_aplicaveis}</p>
        <p><strong className="text-foreground">Alvará indiscriminado:</strong> {regras.regra_alvara_indiscriminado}</p>
        <p><strong className="text-foreground">Captação:</strong> {regras.captacao_criterios}</p>
        <p><strong className="text-foreground">Performance:</strong> {regras.performance_criterios}</p>
        <p className="md:col-span-2"><strong className="text-foreground">Exceções:</strong> {regras.excecoes}</p>
        <p className="md:col-span-2"><strong className="text-foreground">Pagamento devido enquanto:</strong> {regras.condicao_pagamento}</p>
        <div className="md:col-span-2">
          <strong className="text-foreground">Limites temporais por tipo:</strong>
          <ul className="list-disc list-inside ml-2 mt-1">
            {Object.entries(regras.limites_temporais_anos).map(([k, v]) => (
              <li key={k}>{k}: {v === "sem_limite" ? "sem limite" : `${v} anos`}</li>
            ))}
          </ul>
        </div>
      </div>
    </details>
  );
}

// ── Pendentes (Plano B) ──────────────────────────────────────────

function PendentesLista({
  pendentes,
  loading,
  onRefresh,
}: {
  pendentes: ContratoPendente[];
  loading: boolean;
  onRefresh: () => void;
}) {
  const [editing, setEditing] = useState<ContratoPendente | null>(null);

  if (loading) return <div className="text-muted p-6">Carregando...</div>;
  if (!pendentes.length)
    return (
      <div className="text-muted p-6 text-center border border-dashed border-border rounded-lg">
        Nenhum contrato pendente. Todos foram tratados.
      </div>
    );

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted mb-3">
        Contratos sem participação cadastrada OU com rascunho aguardando aprovação do financeiro.
      </p>
      {pendentes.map((c) => (
        <div
          key={c.contract_id}
          className="bg-card border border-border rounded-lg p-4 flex items-center justify-between"
        >
          <div>
            <div className="font-medium">
              {c.client_name || "(sem nome)"}{" "}
              <span className="text-xs text-muted">#{c.contract_id.slice(0, 8)}</span>
            </div>
            <div className="text-xs text-muted mt-1">
              {c.client_email} · Criado por {c.created_by || "—"} em{" "}
              {new Date(c.created_at).toLocaleDateString("pt-BR")}
            </div>
            <div className="text-xs mt-1">
              {c.tem_rascunho ? (
                <span className="text-amber-700">
                  Rascunho · tipo inferido: {c.tipo_honorario_inferido}
                </span>
              ) : (
                <span className="text-red-700">Sem participação cadastrada</span>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            {c.tem_rascunho && c.participacao_id ? (
              <button
                onClick={() => setEditing(c)}
                className="px-3 py-1.5 text-xs bg-primary-dark text-white rounded hover:bg-primary-dark/90"
              >
                Revisar e aprovar
              </button>
            ) : (
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  navigator.clipboard.writeText(c.contract_id);
                  alert(`ID copiado: ${c.contract_id}\nUse na aba "Nova Participação".`);
                }}
                className="px-3 py-1.5 text-xs border border-border rounded hover:bg-gray-50"
              >
                Copiar ID
              </a>
            )}
          </div>
        </div>
      ))}

      {editing && editing.participacao_id && (
        <FormAprovarRascunho
          pendente={editing}
          onClose={() => setEditing(null)}
          onDone={() => {
            setEditing(null);
            onRefresh();
          }}
        />
      )}
    </div>
  );
}

function FormAprovarRascunho({
  pendente,
  onClose,
  onDone,
}: {
  pendente: ContratoPendente;
  onClose: () => void;
  onDone: () => void;
}) {
  const [form, setForm] = useState({
    tipo_honorario: pendente.tipo_honorario_inferido || "mensalidade",
    cliente_cpf_cnpj: pendente.cliente_cpf_cnpj || "",
    percentual_captacao: pendente.percentual_captacao_rascunho ?? 0,
    percentual_performance: pendente.percentual_performance_rascunho ?? 0,
    motivo_captacao: pendente.motivo_captacao_rascunho || "",
    motivo_performance: pendente.motivo_performance_rascunho || "",
    aprovado_por: "",
    natureza: pendente.natureza_rascunho || "contratual",
    observacoes: pendente.observacoes_rascunho || "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const total = form.percentual_captacao + form.percentual_performance;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    setSaving(true);
    try {
      await aprovarParticipacao(pendente.participacao_id!, {
        tipo_honorario: form.tipo_honorario,
        cliente_cpf_cnpj: form.cliente_cpf_cnpj || undefined,
        percentual_captacao: form.percentual_captacao,
        percentual_performance: form.percentual_performance,
        motivo_captacao: form.motivo_captacao || undefined,
        motivo_performance: form.motivo_performance || undefined,
        aprovado_por: form.aprovado_por || undefined,
        natureza: form.natureza,
        observacoes: form.observacoes || undefined,
      });
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Erro");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4 overflow-auto">
      <form
        onSubmit={submit}
        className="bg-card border border-border rounded-lg p-6 max-w-2xl w-full space-y-4 text-sm max-h-[90vh] overflow-auto"
      >
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-foreground">
            Revisar rascunho — {pendente.client_name}
          </h3>
          <button type="button" onClick={onClose} className="text-muted hover:text-foreground">
            ✕
          </button>
        </div>

        <p className="text-xs text-muted">
          Contrato #{pendente.contract_id.slice(0, 8)} · Tipo inferido pelo wizard:{" "}
          <strong>{pendente.tipo_honorario_inferido}</strong>. Ajuste se necessário.
        </p>

        <Row>
          <Field label="Tipo de honorário">
            <select
              value={form.tipo_honorario}
              onChange={(e) => setForm({ ...form, tipo_honorario: e.target.value })}
              className="input"
            >
              {TIPOS_HONORARIO.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="CPF/CNPJ cliente">
            <input
              value={form.cliente_cpf_cnpj}
              onChange={(e) => setForm({ ...form, cliente_cpf_cnpj: e.target.value })}
              className="input"
            />
          </Field>
        </Row>

        <Row>
          <Field label="Captação % (máx 20)">
            <input
              type="number"
              min={0}
              max={20}
              step={0.5}
              value={form.percentual_captacao}
              onChange={(e) =>
                setForm({ ...form, percentual_captacao: parseFloat(e.target.value) || 0 })
              }
              className="input"
            />
          </Field>
          <Field label="Performance % (máx 20)">
            <input
              type="number"
              min={0}
              max={20}
              step={0.5}
              value={form.percentual_performance}
              onChange={(e) =>
                setForm({ ...form, percentual_performance: parseFloat(e.target.value) || 0 })
              }
              className="input"
            />
          </Field>
          <Field label="Total">
            <div className={`input bg-gray-100 ${total > 40 ? "text-red-700 font-bold" : ""}`}>
              {total.toFixed(2)}%
            </div>
          </Field>
        </Row>

        {form.percentual_captacao > 0 && (
          <Field label="Motivo Captação">
            <textarea
              rows={2}
              value={form.motivo_captacao}
              onChange={(e) => setForm({ ...form, motivo_captacao: e.target.value })}
              className="input"
            />
          </Field>
        )}

        {form.percentual_performance > 0 && (
          <>
            <Field label="Motivo Performance *">
              <textarea
                rows={2}
                value={form.motivo_performance}
                onChange={(e) => setForm({ ...form, motivo_performance: e.target.value })}
                className="input"
                required
              />
            </Field>
            <Field label="Aprovado por (sócios) *">
              <input
                value={form.aprovado_por}
                onChange={(e) => setForm({ ...form, aprovado_por: e.target.value })}
                className="input"
                required
              />
            </Field>
          </>
        )}

        <Row>
          <Field label="Natureza">
            <select
              value={form.natureza}
              onChange={(e) => setForm({ ...form, natureza: e.target.value })}
              className="input"
            >
              <option value="contratual">Contratual</option>
              <option value="societario">Societário</option>
            </select>
          </Field>
        </Row>

        <Field label="Observações">
          <textarea
            rows={2}
            value={form.observacoes}
            onChange={(e) => setForm({ ...form, observacoes: e.target.value })}
            className="input"
          />
        </Field>

        {err && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800">
            {err}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-border rounded-lg text-sm"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-primary-dark text-white rounded-lg font-medium disabled:opacity-50"
          >
            {saving ? "Aprovando..." : "Aprovar e ativar"}
          </button>
        </div>

        <style jsx>{`
          :global(.input) {
            width: 100%;
            padding: 0.5rem 0.75rem;
            border: 1px solid var(--border, #e5e7eb);
            border-radius: 0.5rem;
            background: white;
            font-size: 0.875rem;
          }
        `}</style>
      </form>
    </div>
  );
}

// ── Lista + Detalhes ─────────────────────────────────────────────

function ListaParticipacoes({
  items,
  loading,
  onRefresh,
}: {
  items: Participacao[];
  loading: boolean;
  onRefresh: () => void;
}) {
  const [openId, setOpenId] = useState<number | null>(null);

  if (loading) return <div className="text-muted p-6">Carregando...</div>;
  if (!items.length)
    return (
      <div className="text-muted p-6 text-center border border-dashed border-border rounded-lg">
        Nenhuma participação cadastrada.
      </div>
    );

  return (
    <div className="space-y-3">
      {items.map((p) => (
        <div key={p.id} className="bg-card border border-border rounded-lg overflow-hidden">
          <button
            onClick={() => setOpenId(openId === p.id ? null : p.id)}
            className="w-full text-left px-4 py-3 hover:bg-gray-50/50 transition flex items-center justify-between"
          >
            <div>
              <div className="font-medium text-foreground">
                {p.beneficiario_nome || p.beneficiario_email}
                <span className="ml-2 text-xs text-muted">#{p.contract_id}</span>
              </div>
              <div className="text-xs text-muted mt-1">
                {p.tipo_honorario.toUpperCase()} · Captação {p.percentual_captacao}% · Performance{" "}
                {p.percentual_performance}% · Total {p.percentual_total}%
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm font-medium">{brl(p.total_pago)}</div>
              <div className="text-xs text-muted">
                {p.vinculo_ativo ? (
                  <span className="text-green-700">vínculo ativo</span>
                ) : (
                  <span className="text-red-700">encerrado</span>
                )}
              </div>
            </div>
          </button>
          {openId === p.id && <DetalheParticipacao participacao={p} onRefresh={onRefresh} />}
        </div>
      ))}
    </div>
  );
}

function DetalheParticipacao({
  participacao,
  onRefresh,
}: {
  participacao: Participacao;
  onRefresh: () => void;
}) {
  const [resumo, setResumo] = useState<ResumoParticipacao | null>(null);
  const [showPag, setShowPag] = useState(false);

  const reload = useCallback(async () => {
    const r = await getResumoParticipacao(participacao.id);
    setResumo(r);
  }, [participacao.id]);

  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <div className="border-t border-border bg-gray-50/30 p-4 space-y-4">
      <div className="grid md:grid-cols-2 gap-3 text-sm">
        <Info label="Data início" value={participacao.data_inicio} />
        <Info
          label="Limite temporal"
          value={
            participacao.limite_temporal_anos
              ? `${participacao.limite_temporal_anos} ano(s) — até ${participacao.data_limite_temporal}`
              : "sem limite"
          }
        />
        <Info label="Natureza" value={participacao.natureza} />
        <Info label="Cliente CPF/CNPJ" value={participacao.cliente_cpf_cnpj || "—"} />
        {participacao.motivo_captacao && (
          <Info label="Motivo Captação" value={participacao.motivo_captacao} />
        )}
        {participacao.motivo_performance && (
          <Info label="Motivo Performance" value={participacao.motivo_performance} />
        )}
        {participacao.aprovado_por && (
          <Info label="Aprovado por" value={participacao.aprovado_por} />
        )}
      </div>

      {resumo && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-medium text-sm">
              Pagamentos ({resumo.pagamentos.length}) — Total participação: {brl(resumo.total_participacao)}
            </h4>
            <button
              onClick={() => setShowPag(!showPag)}
              className="text-xs text-accent hover:underline"
            >
              {showPag ? "Cancelar" : "+ Registrar recebimento"}
            </button>
          </div>

          {showPag && (
            <FormPagamento
              participacaoId={participacao.id}
              onDone={() => {
                setShowPag(false);
                reload();
                onRefresh();
              }}
            />
          )}

          {resumo.pagamentos.length > 0 && (
            <table className="w-full text-xs mt-2">
              <thead>
                <tr className="text-muted border-b border-border">
                  <th className="text-left py-1">Data</th>
                  <th className="text-left py-1">NF</th>
                  <th className="text-left py-1">Parcela</th>
                  <th className="text-right py-1">Líquido contratual</th>
                  <th className="text-right py-1">Participação</th>
                  <th className="text-left py-1">Status</th>
                  <th className="text-left py-1">Obs.</th>
                </tr>
              </thead>
              <tbody>
                {resumo.pagamentos.map((pg) => (
                  <tr key={pg.id} className={`border-b border-border/40 ${rowBgByStatus(pg.status)}`}>
                    <td className="py-1">{pg.data_recebimento}</td>
                    <td className="py-1 font-mono text-[10px]">{pg.nf_referencia || "—"}</td>
                    <td className="py-1">
                      {pg.parcela_total > 1
                        ? `${pg.parcela_num}/${pg.parcela_total}`
                        : "Única"}
                    </td>
                    <td className="py-1 text-right">{brl(pg.valor_liquido_recebido)}</td>
                    <td className={`py-1 text-right ${pg.valor_participacao === 0 ? "text-red-700" : ""}`}>
                      {brl(pg.valor_participacao)}
                    </td>
                    <td className="py-1">
                      <StatusSelect
                        value={pg.status}
                        onChange={async (next) => {
                          try {
                            await atualizarStatusPagamento(pg.id, next);
                            reload();
                          } catch (e) {
                            alert(e instanceof Error ? e.message : "Erro ao atualizar status");
                          }
                        }}
                      />
                    </td>
                    <td className="py-1 text-muted">{pg.observacoes || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {participacao.vinculo_ativo && (
        <button
          onClick={async () => {
            const data = prompt("Data de encerramento do vínculo (YYYY-MM-DD):");
            if (!data) return;
            try {
              await encerrarVinculo(participacao.id, data);
              onRefresh();
            } catch (e) {
              alert(e instanceof Error ? e.message : "Erro");
            }
          }}
          className="text-xs text-red-700 hover:underline"
        >
          Encerrar vínculo
        </button>
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="text-sm text-foreground">{value}</div>
    </div>
  );
}

// ── Form Nova ────────────────────────────────────────────────────

function FormNovaParticipacao({
  onCreated,
  setTab,
}: {
  onCreated: () => void;
  setTab: (t: "lista" | "nova" | "simular") => void;
}) {
  const [form, setForm] = useState({
    contract_id: "",
    beneficiario_email: "",
    beneficiario_nome: "",
    tipo_honorario: "hora",
    percentual_captacao: 0,
    percentual_performance: 0,
    motivo_captacao: "",
    motivo_performance: "",
    natureza: "contratual",
    cliente_cpf_cnpj: "",
    data_inicio: new Date().toISOString().slice(0, 10),
    aprovado_por: "",
    observacoes: "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const total = form.percentual_captacao + form.percentual_performance;
  const validClient = useMemo(() => {
    const errs: string[] = [];
    if (form.percentual_captacao > 20) errs.push("Captação > 20%");
    if (form.percentual_performance > 20) errs.push("Performance > 20%");
    if (total > 40) errs.push("Soma > 40%");
    if (new Date(form.data_inicio) < new Date("2024-08-01")) errs.push("Início < 2024-08-01 (sem retroatividade)");
    if (form.percentual_captacao > 0 && !form.cliente_cpf_cnpj)
      errs.push("Captação exige CPF/CNPJ");
    if (form.percentual_performance > 0 && (!form.motivo_performance || !form.aprovado_por))
      errs.push("Performance exige motivo e aprovado_por");
    return errs;
  }, [form, total]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    setSaving(true);
    try {
      await createParticipacao({
        ...form,
        motivo_captacao: form.motivo_captacao || undefined,
        motivo_performance: form.motivo_performance || undefined,
        cliente_cpf_cnpj: form.cliente_cpf_cnpj || undefined,
        aprovado_por: form.aprovado_por || undefined,
        observacoes: form.observacoes || undefined,
      });
      onCreated();
      setTab("lista");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Erro");
    } finally {
      setSaving(false);
    }
  };

  const upd = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm({ ...form, [k]: v });

  return (
    <form onSubmit={submit} className="bg-card border border-border rounded-lg p-6 space-y-4 text-sm">
      <Row>
        <Field label="ID do contrato *">
          <input
            required
            value={form.contract_id}
            onChange={(e) => upd("contract_id", e.target.value)}
            className="input"
          />
        </Field>
        <Field label="Tipo de honorário *">
          <select
            value={form.tipo_honorario}
            onChange={(e) => upd("tipo_honorario", e.target.value)}
            className="input"
          >
            {TIPOS_HONORARIO.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </Field>
      </Row>

      <Row>
        <Field label="Beneficiário — e-mail *">
          <input
            required
            type="email"
            value={form.beneficiario_email}
            onChange={(e) => upd("beneficiario_email", e.target.value)}
            className="input"
          />
        </Field>
        <Field label="Beneficiário — nome">
          <input
            value={form.beneficiario_nome}
            onChange={(e) => upd("beneficiario_nome", e.target.value)}
            className="input"
          />
        </Field>
      </Row>

      <Row>
        <Field label="Captação (% — máx 20)">
          <input
            type="number"
            min={0}
            max={20}
            step={0.5}
            value={form.percentual_captacao}
            onChange={(e) => upd("percentual_captacao", parseFloat(e.target.value) || 0)}
            className="input"
          />
        </Field>
        <Field label="Performance (% — máx 20)">
          <input
            type="number"
            min={0}
            max={20}
            step={0.5}
            value={form.percentual_performance}
            onChange={(e) => upd("percentual_performance", parseFloat(e.target.value) || 0)}
            className="input"
          />
        </Field>
        <Field label="Total">
          <div className={`input bg-gray-100 ${total > 40 ? "text-red-700 font-bold" : ""}`}>
            {total.toFixed(2)}% {total > 40 && "(excede 40%)"}
          </div>
        </Field>
      </Row>

      {form.percentual_captacao > 0 && (
        <>
          <Field label="CPF/CNPJ do cliente (obrigatório p/ captação) *">
            <input
              value={form.cliente_cpf_cnpj}
              onChange={(e) => upd("cliente_cpf_cnpj", e.target.value)}
              className="input"
              placeholder="Necessário p/ checar 36 meses sem faturamento"
            />
          </Field>
          <Field label="Motivo da captação">
            <textarea
              rows={2}
              value={form.motivo_captacao}
              onChange={(e) => upd("motivo_captacao", e.target.value)}
              className="input"
            />
          </Field>
        </>
      )}

      {form.percentual_performance > 0 && (
        <>
          <Field label="Motivo da performance * (atuação excepcional OU nova área)">
            <textarea
              rows={2}
              value={form.motivo_performance}
              onChange={(e) => upd("motivo_performance", e.target.value)}
              className="input"
              required
            />
          </Field>
          <Field label="Aprovado por (sócios) *">
            <input
              value={form.aprovado_por}
              onChange={(e) => upd("aprovado_por", e.target.value)}
              className="input"
              required
            />
          </Field>
        </>
      )}

      <Row>
        <Field label="Natureza do vínculo">
          <select
            value={form.natureza}
            onChange={(e) => upd("natureza", e.target.value)}
            className="input"
          >
            <option value="contratual">Contratual</option>
            <option value="societario">Societário</option>
          </select>
        </Field>
        <Field label="Data de início *">
          <input
            type="date"
            required
            min="2024-08-01"
            value={form.data_inicio}
            onChange={(e) => upd("data_inicio", e.target.value)}
            className="input"
          />
        </Field>
      </Row>

      <Field label="Observações">
        <textarea
          rows={2}
          value={form.observacoes}
          onChange={(e) => upd("observacoes", e.target.value)}
          className="input"
        />
      </Field>

      {validClient.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          {validClient.join(" · ")}
        </div>
      )}
      {err && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800">
          {err}
        </div>
      )}

      <button
        type="submit"
        disabled={saving || validClient.length > 0}
        className="px-4 py-2 bg-primary-dark text-white rounded-lg font-medium hover:bg-primary-dark/90 disabled:opacity-50"
      >
        {saving ? "Salvando..." : "Cadastrar Participação"}
      </button>

      <style jsx>{`
        :global(.input) {
          width: 100%;
          padding: 0.5rem 0.75rem;
          border: 1px solid var(--border, #e5e7eb);
          border-radius: 0.5rem;
          background: white;
          font-size: 0.875rem;
        }
      `}</style>
    </form>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return <div className="grid md:grid-cols-3 gap-3">{children}</div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs text-muted block mb-1">{label}</span>
      {children}
    </label>
  );
}

// ── Form Pagamento ───────────────────────────────────────────────

function FormPagamento({
  participacaoId,
  onDone,
}: {
  participacaoId: number;
  onDone: () => void;
}) {
  const [form, setForm] = useState({
    data_recebimento: new Date().toISOString().slice(0, 10),
    valor_bruto: 0,
    discriminado: true,
    valor_contratual: 0,
    observacoes: "",
    parcela_num: 1,
    parcela_total: 1,
    nf_referencia: "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    setSaving(true);
    try {
      await registrarPagamento(participacaoId, {
        data_recebimento: form.data_recebimento,
        valor_bruto: form.valor_bruto,
        discriminado: form.discriminado,
        valor_contratual: form.discriminado ? form.valor_contratual : undefined,
        observacoes: form.observacoes || undefined,
        parcela_num: form.parcela_num,
        parcela_total: form.parcela_total,
        nf_referencia: form.nf_referencia || undefined,
      });
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Erro");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="bg-white border border-border rounded-lg p-4 space-y-3 text-xs"
    >
      <div className="grid grid-cols-2 gap-2">
        <label>
          <span className="block text-muted mb-1">Data recebimento</span>
          <input
            type="date"
            required
            value={form.data_recebimento}
            onChange={(e) => setForm({ ...form, data_recebimento: e.target.value })}
            className="input"
          />
        </label>
        <label>
          <span className="block text-muted mb-1">Valor bruto recebido (R$)</span>
          <input
            type="number"
            step={0.01}
            required
            value={form.valor_bruto}
            onChange={(e) => setForm({ ...form, valor_bruto: parseFloat(e.target.value) || 0 })}
            className="input"
          />
        </label>
      </div>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={form.discriminado}
          onChange={(e) => setForm({ ...form, discriminado: e.target.checked })}
        />
        <span>Alvará/acordo discrimina parcela contratual?</span>
      </label>

      {form.discriminado ? (
        <label>
          <span className="block text-muted mb-1">Parcela contratual (R$)</span>
          <input
            type="number"
            step={0.01}
            value={form.valor_contratual}
            onChange={(e) => setForm({ ...form, valor_contratual: parseFloat(e.target.value) || 0 })}
            className="input"
          />
        </label>
      ) : (
        <p className="text-muted">Sem discriminação → 50% contratual / 50% sucumbencial.</p>
      )}

      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-border/40">
        <label>
          <span className="block text-muted mb-1">Parcela nº</span>
          <input
            type="number"
            min={1}
            value={form.parcela_num}
            onChange={(e) => setForm({ ...form, parcela_num: parseInt(e.target.value) || 1 })}
            className="input"
          />
        </label>
        <label>
          <span className="block text-muted mb-1">Total parcelas</span>
          <input
            type="number"
            min={1}
            value={form.parcela_total}
            onChange={(e) => setForm({ ...form, parcela_total: parseInt(e.target.value) || 1 })}
            className="input"
          />
        </label>
        <label>
          <span className="block text-muted mb-1">NF referência</span>
          <input
            value={form.nf_referencia}
            onChange={(e) => setForm({ ...form, nf_referencia: e.target.value })}
            placeholder="NF2026.XXX ou emitir"
            className="input"
          />
        </label>
      </div>

      <label>
        <span className="block text-muted mb-1">Observações</span>
        <input
          value={form.observacoes}
          onChange={(e) => setForm({ ...form, observacoes: e.target.value })}
          className="input"
        />
      </label>

      {err && (
        <div className="rounded border border-red-200 bg-red-50 p-2 text-red-800">{err}</div>
      )}

      <button
        type="submit"
        disabled={saving}
        className="px-3 py-1.5 bg-primary-dark text-white rounded font-medium hover:bg-primary-dark/90 disabled:opacity-50"
      >
        {saving ? "Calculando..." : "Registrar e calcular participação"}
      </button>
    </form>
  );
}

// ── Simulador ───────────────────────────────────────────────────

function Simulador() {
  const [form, setForm] = useState({
    tipo_honorario: "hora",
    percentual_captacao: 10,
    percentual_performance: 0,
    data_inicio_participacao: "2024-08-01",
    data_recebimento: new Date().toISOString().slice(0, 10),
    valor_liquido_recebido: 10000,
    vinculo_ativo: true,
    data_fim_vinculo: "",
    eh_contratual: true,
  });
  const [result, setResult] = useState<null | {
    valor_participacao: number;
    dentro_limite_temporal: boolean;
    vinculo_ativo: boolean;
    motivo_zerado: string | null;
    percentual_aplicado: number;
  }>(null);
  const [err, setErr] = useState("");

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    try {
      const r = await simularParticipacao({
        ...form,
        data_fim_vinculo: form.data_fim_vinculo || undefined,
      });
      setResult(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Erro");
    }
  };

  return (
    <form onSubmit={run} className="bg-card border border-border rounded-lg p-6 space-y-3 text-sm">
      <p className="text-muted text-xs">
        Calcule a participação sobre um valor líquido recebido, sem persistir nada.
      </p>
      <div className="grid md:grid-cols-3 gap-3">
        <Field label="Tipo honorário">
          <select
            value={form.tipo_honorario}
            onChange={(e) => setForm({ ...form, tipo_honorario: e.target.value })}
            className="input"
          >
            {TIPOS_HONORARIO.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Captação %">
          <input
            type="number"
            step={0.5}
            value={form.percentual_captacao}
            onChange={(e) => setForm({ ...form, percentual_captacao: parseFloat(e.target.value) || 0 })}
            className="input"
          />
        </Field>
        <Field label="Performance %">
          <input
            type="number"
            step={0.5}
            value={form.percentual_performance}
            onChange={(e) => setForm({ ...form, percentual_performance: parseFloat(e.target.value) || 0 })}
            className="input"
          />
        </Field>
        <Field label="Data início participação">
          <input
            type="date"
            value={form.data_inicio_participacao}
            onChange={(e) => setForm({ ...form, data_inicio_participacao: e.target.value })}
            className="input"
          />
        </Field>
        <Field label="Data do recebimento">
          <input
            type="date"
            value={form.data_recebimento}
            onChange={(e) => setForm({ ...form, data_recebimento: e.target.value })}
            className="input"
          />
        </Field>
        <Field label="Valor líquido contratual (R$)">
          <input
            type="number"
            step={0.01}
            value={form.valor_liquido_recebido}
            onChange={(e) => setForm({ ...form, valor_liquido_recebido: parseFloat(e.target.value) || 0 })}
            className="input"
          />
        </Field>
        <Field label="Vínculo ativo?">
          <select
            value={form.vinculo_ativo ? "1" : "0"}
            onChange={(e) => setForm({ ...form, vinculo_ativo: e.target.value === "1" })}
            className="input"
          >
            <option value="1">Sim</option>
            <option value="0">Não</option>
          </select>
        </Field>
        <Field label="Data fim vínculo (opcional)">
          <input
            type="date"
            value={form.data_fim_vinculo}
            onChange={(e) => setForm({ ...form, data_fim_vinculo: e.target.value })}
            className="input"
          />
        </Field>
        <Field label="É contratual?">
          <select
            value={form.eh_contratual ? "1" : "0"}
            onChange={(e) => setForm({ ...form, eh_contratual: e.target.value === "1" })}
            className="input"
          >
            <option value="1">Sim (contratual)</option>
            <option value="0">Não (sucumbencial — não gera participação)</option>
          </select>
        </Field>
      </div>

      {err && (
        <div className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-800">{err}</div>
      )}

      <button
        type="submit"
        className="px-4 py-2 bg-primary-dark text-white rounded-lg font-medium hover:bg-primary-dark/90"
      >
        Calcular
      </button>

      {result && (
        <div
          className={`mt-4 p-4 rounded-lg border ${
            result.valor_participacao > 0
              ? "border-green-200 bg-green-50"
              : "border-amber-200 bg-amber-50"
          }`}
        >
          <p className="text-lg font-bold">
            Participação: {brl(result.valor_participacao)}
          </p>
          <p className="text-xs text-muted mt-1">
            Percentual aplicado: {result.percentual_aplicado}% · Dentro limite temporal:{" "}
            {result.dentro_limite_temporal ? "sim" : "não"} · Vínculo:{" "}
            {result.vinculo_ativo ? "ativo" : "encerrado"}
          </p>
          {result.motivo_zerado && (
            <p className="text-xs text-amber-900 mt-2">Motivo zerado: {result.motivo_zerado}</p>
          )}
        </div>
      )}

      <style jsx>{`
        :global(.input) {
          width: 100%;
          padding: 0.5rem 0.75rem;
          border: 1px solid var(--border, #e5e7eb);
          border-radius: 0.5rem;
          background: white;
          font-size: 0.875rem;
        }
      `}</style>
    </form>
  );
}
