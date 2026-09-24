"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuthStatus } from "@/app/lib/useAuthStatus";
import {
  listTestemunhas,
  createTestemunha,
  updateTestemunha,
  type Testemunha,
} from "@/app/lib/api";

// Remove acentos pra busca "monica" achar "Mônica" tambem.
function semAcento(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "");
}

export default function TestemunhasPage() {
  const sessionStatus = useAuthStatus();
  const [rows, setRows] = useState<Testemunha[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [busca, setBusca] = useState("");
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

  const buscaNormalizada = semAcento(busca.trim().toLowerCase());
  const filteredRows = buscaNormalizada
    ? rows.filter((t) => semAcento(t.nome.toLowerCase()).includes(buscaNormalizada))
    : rows;

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

      <div className="flex flex-wrap items-center gap-3 mb-3">
        <input
          type="text"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar por nome..."
          className="flex-1 min-w-48 px-3 py-2 border border-border bg-card text-foreground rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary/40"
        />
        <label className="flex items-center gap-2 text-sm text-muted cursor-pointer">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
          />
          Mostrar inativas
        </label>
      </div>

      {loading ? (
        <p className="text-sm text-muted">Carregando...</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted">Nenhuma testemunha cadastrada.</p>
      ) : filteredRows.length === 0 ? (
        <p className="text-sm text-muted">Nenhuma testemunha encontrada para &quot;{busca}&quot;.</p>
      ) : (
        <div className="space-y-2">
          {filteredRows.map((t) => (
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
