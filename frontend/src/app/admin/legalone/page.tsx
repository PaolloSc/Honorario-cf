"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuthStatus } from "@/app/lib/useAuthStatus";
import {
  listLegalOneOpcoes,
  createLegalOneOpcao,
  updateLegalOneOpcao,
  LEGALONE_TIPOS,
  type LegalOneOpcoes,
  type LegalOneTipo,
} from "@/app/lib/api";

const VAZIO: LegalOneOpcoes = {
  categoria_cliente: [],
  etiqueta: [],
  lista_transmissao: [],
};

export default function LegalOneAdminPage() {
  const sessionStatus = useAuthStatus();
  const [opcoes, setOpcoes] = useState<LegalOneOpcoes>(VAZIO);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [accessDenied, setAccessDenied] = useState(false);
  const [novos, setNovos] = useState<Record<string, string>>({});
  const [salvando, setSalvando] = useState<LegalOneTipo | null>(null);

  const fetchRows = useCallback(async () => {
    setLoading(true);
    try {
      setOpcoes(await listLegalOneOpcoes(true));
      setError("");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erro ao carregar opções";
      if (msg.includes("403")) setAccessDenied(true);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (sessionStatus === "authenticated") fetchRows();
  }, [fetchRows, sessionStatus]);

  const adicionar = async (tipo: LegalOneTipo) => {
    const valor = (novos[tipo] ?? "").trim();
    if (!valor) return;
    setSalvando(tipo);
    try {
      await createLegalOneOpcao({ tipo, valor });
      setNovos((n) => ({ ...n, [tipo]: "" }));
      setError("");
      fetchRows();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao adicionar opção");
    } finally {
      setSalvando(null);
    }
  };

  const alternar = async (id: number, ativo: boolean) => {
    try {
      await updateLegalOneOpcao(id, !ativo);
      fetchRows();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao atualizar opção");
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
        Legal One
      </h1>
      <p className="text-sm text-muted mb-6">
        Opções das tabelas do Legal One oferecidas na etapa 5 do wizard e repassadas ao
        financeiro. Desativar uma opção a remove do wizard sem alterar contratos já
        registrados.
      </p>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-danger/[0.08] border border-danger text-sm text-danger">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-muted">Carregando...</p>
      ) : (
        <div className="space-y-6">
          {LEGALONE_TIPOS.map(({ value: tipo, label }) => (
            <div key={tipo} className="bg-card rounded-xl border border-border shadow-sm p-4">
              <h2 className="text-sm font-semibold text-foreground mb-3">{label}</h2>

              <div className="flex flex-wrap gap-2 mb-4">
                <input
                  type="text"
                  value={novos[tipo] ?? ""}
                  onChange={(e) => setNovos((n) => ({ ...n, [tipo]: e.target.value }))}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") adicionar(tipo);
                  }}
                  placeholder={`Nova ${label.toLowerCase()}`}
                  className="flex-1 min-w-48 px-3 py-2 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-primary/40"
                />
                <button
                  onClick={() => adicionar(tipo)}
                  disabled={salvando === tipo || !(novos[tipo] ?? "").trim()}
                  className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition"
                >
                  {salvando === tipo ? "Salvando..." : "Adicionar"}
                </button>
              </div>

              {opcoes[tipo].length === 0 ? (
                <p className="text-sm text-muted">Nenhuma opção cadastrada.</p>
              ) : (
                <ul className="divide-y divide-border/50">
                  {opcoes[tipo].map((o) => (
                    <li key={o.id} className="flex items-center justify-between py-2">
                      <span className={o.ativo ? "text-sm" : "text-sm text-muted line-through"}>
                        {o.valor}
                      </span>
                      <button
                        onClick={() => alternar(o.id, o.ativo)}
                        className="text-xs font-medium text-accent hover:underline"
                      >
                        {o.ativo ? "Desativar" : "Reativar"}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
