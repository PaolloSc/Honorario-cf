"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuthStatus } from "@/app/lib/useAuthStatus";
import {
  listColaboradoresAdmin,
  createColaborador,
  updateColaborador,
  deleteColaborador,
  PAPEIS_COLABORADOR,
  type Colaborador,
} from "@/app/lib/api";

const PAPEL_LABEL: Record<string, string> = Object.fromEntries(
  PAPEIS_COLABORADOR.map((p) => [p.value, p.label])
);

export default function ColaboradoresAdminPage() {
  const sessionStatus = useAuthStatus();
  const [rows, setRows] = useState<Colaborador[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [accessDenied, setAccessDenied] = useState(false);

  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [papel, setPapel] = useState("advogado");
  const [saving, setSaving] = useState(false);

  const fetchRows = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listColaboradoresAdmin(true);
      setRows(r.colaboradores);
      setError("");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erro ao carregar colaboradores";
      if (msg.includes("403")) setAccessDenied(true);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (sessionStatus === "authenticated") fetchRows();
  }, [fetchRows, sessionStatus]);

  const handleCreate = async () => {
    if (!nome.trim()) return;
    setSaving(true);
    try {
      await createColaborador({
        nome: nome.trim(),
        email: email.trim() || null,
        papel,
      });
      setNome("");
      setEmail("");
      setPapel("advogado");
      fetchRows();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao criar colaborador");
    } finally {
      setSaving(false);
    }
  };

  const toggleAtivo = async (c: Colaborador) => {
    try {
      if (c.ativo) await deleteColaborador(c.id);
      else await updateColaborador(c.id, { ativo: true });
      fetchRows();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao atualizar");
    }
  };

  const changePapel = async (c: Colaborador, novoPapel: string) => {
    try {
      await updateColaborador(c.id, { papel: novoPapel });
      fetchRows();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao atualizar papel");
    }
  };

  if (accessDenied) {
    return (
      <div className="max-w-xl mx-auto mt-16 p-8 bg-danger/[0.08] border border-danger rounded-lg text-center">
        <h2 className="text-lg font-semibold text-danger mb-2">Acesso Restrito</h2>
        <p className="text-danger">Você não tem permissão para acessar esta página.</p>
        <a href="/" className="mt-4 inline-block text-sm text-primary hover:underline">
          Voltar ao início
        </a>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="font-display text-2xl font-semibold text-primary-dark tracking-wide mb-1">
        Colaboradores
      </h1>
      <p className="text-sm text-muted mb-6">
        Roster do escritório. Advogados e sócios aparecem nas listas suspensas do
        wizard (campo &quot;Para quem&quot; e responsáveis).
      </p>

      {error && !accessDenied && (
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
            placeholder="email@exemplo.com (opcional)"
            className="flex-1 min-w-48 px-3 py-2 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-primary/40"
          />
          <select
            value={papel}
            onChange={(e) => setPapel(e.target.value)}
            className="px-3 py-2 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-primary/40"
          >
            {PAPEIS_COLABORADOR.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
          <button
            onClick={handleCreate}
            disabled={saving || !nome.trim()}
            className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition"
          >
            {saving ? "Salvando..." : "Adicionar"}
          </button>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-muted">Carregando...</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted">Nenhum colaborador cadastrado.</p>
      ) : (
        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-background/60">
                <th className="text-left px-4 py-3 font-medium text-muted">Nome</th>
                <th className="text-left px-4 py-3 font-medium text-muted">E-mail</th>
                <th className="text-left px-4 py-3 font-medium text-muted">Papel</th>
                <th className="text-left px-4 py-3 font-medium text-muted">Status</th>
                <th className="text-right px-4 py-3 font-medium text-muted">Ações</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} className="border-b border-border/50 hover:bg-background/60">
                  <td className="px-4 py-3 font-medium">
                    {c.nome}
                    {c.participavel && (
                      <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-primary/[0.16] text-primary-dark">
                        wizard
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted">{c.email || "—"}</td>
                  <td className="px-4 py-3">
                    <select
                      value={c.papel}
                      onChange={(e) => changePapel(c, e.target.value)}
                      className="text-xs border border-border bg-card text-foreground rounded px-2 py-1"
                    >
                      {PAPEIS_COLABORADOR.map((p) => (
                        <option key={p.value} value={p.value}>
                          {PAPEL_LABEL[p.value]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        c.ativo ? "bg-primary/[0.16] text-primary-dark" : "bg-border/35 text-muted"
                      }`}
                    >
                      {c.ativo ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => toggleAtivo(c)}
                      className="text-xs font-medium text-accent hover:underline"
                    >
                      {c.ativo ? "Desativar" : "Reativar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
