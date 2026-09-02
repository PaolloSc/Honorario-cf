"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuthStatus } from "@/app/lib/useAuthStatus";
import {
  listTestemunhas,
  createTestemunha,
  updateTestemunha,
  type Testemunha,
} from "@/app/lib/api";

export default function TestemunhasPage() {
  const sessionStatus = useAuthStatus();
  const [rows, setRows] = useState<Testemunha[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [saving, setSaving] = useState(false);

  const fetchRows = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listTestemunhas(showInactive);
      setRows(r.testemunhas);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar testemunhas");
    } finally {
      setLoading(false);
    }
  }, [showInactive]);

  useEffect(() => {
    if (sessionStatus === "authenticated") fetchRows();
  }, [fetchRows, sessionStatus]);

  const handleCreate = async () => {
    if (!nome.trim() || !email.trim()) return;
    setSaving(true);
    try {
      await createTestemunha({ nome: nome.trim(), email: email.trim() });
      setNome("");
      setEmail("");
      fetchRows();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao criar testemunha");
    } finally {
      setSaving(false);
    }
  };

  const toggleAtivo = async (t: Testemunha) => {
    try {
      await updateTestemunha(t.id, { ativo: !t.ativo });
      fetchRows();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao atualizar");
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="font-display text-xl font-semibold text-foreground mb-1">
        Cadastro de Testemunhas
      </h1>
      <p className="text-sm text-muted mb-6">
        Testemunhas recorrentes do escritório. Selecionáveis no envio para assinatura.
        A Testemunha 1 (financeiro) é incluída automaticamente em todo contrato.
      </p>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-danger/[0.08] border border-danger text-sm text-danger">
          {error}
        </div>
      )}

      {/* Create form */}
      <div className="mb-6 p-4 rounded-xl bg-background border border-border">
        <div className="flex flex-wrap gap-2">
          <input
            type="text"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Nome"
            className="flex-1 min-w-40 px-3 py-2 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-primary/40"
          />
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="email@exemplo.com"
            className="flex-1 min-w-48 px-3 py-2 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-primary/40"
          />
          <button
            onClick={handleCreate}
            disabled={saving || !nome.trim() || !email.trim()}
            className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition"
          >
            {saving ? "Salvando..." : "Adicionar"}
          </button>
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm text-muted mb-3 cursor-pointer">
        <input
          type="checkbox"
          checked={showInactive}
          onChange={(e) => setShowInactive(e.target.checked)}
        />
        Mostrar inativas
      </label>

      {loading ? (
        <p className="text-sm text-muted">Carregando...</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted">Nenhuma testemunha cadastrada.</p>
      ) : (
        <div className="space-y-2">
          {rows.map((t) => (
            <div
              key={t.id}
              className="flex items-center gap-3 px-4 py-3 rounded-lg border border-border bg-card"
            >
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">{t.nome}</p>
                <p className="text-xs text-muted">{t.email}</p>
              </div>
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  t.ativo ? "bg-primary/[0.16] text-primary-dark" : "bg-border/35 text-muted"
                }`}
              >
                {t.ativo ? "Ativa" : "Inativa"}
              </span>
              <button
                onClick={() => toggleAtivo(t)}
                className="text-xs font-medium text-accent hover:underline"
              >
                {t.ativo ? "Desativar" : "Reativar"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
