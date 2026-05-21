"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { nfseApi, type NFSeOut } from "@/app/lib/nfse-api";
import { VincularModal } from "./VincularModal";

function brl(v: string) {
  return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const statusBadge: Record<NFSeOut["status_matching"], { label: string; cls: string }> = {
  auto: { label: "✓ auto", cls: "bg-green-100 text-green-800" },
  manual: { label: "✓ manual", cls: "bg-green-100 text-green-800" },
  pendente: { label: "⚠ pendente", cls: "bg-amber-100 text-amber-800" },
  sem_match: { label: "✗ sem match", cls: "bg-red-100 text-red-800" },
  erro: { label: "✗ erro", cls: "bg-red-100 text-red-800" },
  cancelada: { label: "🚫 cancelada", cls: "bg-gray-200 text-gray-700" },
};

export function NotasFiscaisLista({ competencia_mes }: { competencia_mes: string }) {
  const [items, setItems] = useState<NFSeOut[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [editing, setEditing] = useState<NFSeOut | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    nfseApi
      .listar({ competencia_mes, status: statusFilter || undefined })
      .then(setItems)
      .finally(() => setLoading(false));
  }, [competencia_mes, statusFilter]);

  useEffect(() => { refresh(); }, [refresh]);

  const resumo = useMemo(() => {
    const counts: Record<string, number> = {};
    items.forEach((n) => { counts[n.status_matching] = (counts[n.status_matching] || 0) + 1; });
    return counts;
  }, [items]);

  if (loading) return <div className="text-muted p-6">Carregando NFs...</div>;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-xs">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-border rounded px-2 py-1"
        >
          <option value="">Todos status</option>
          <option value="auto">Auto</option>
          <option value="manual">Manual</option>
          <option value="pendente">Pendente</option>
          <option value="sem_match">Sem match</option>
          <option value="cancelada">Cancelada</option>
        </select>
        <span className="text-muted">
          Resumo:{" "}
          {(["auto","manual","pendente","sem_match","cancelada"] as const)
            .map((k) => `${resumo[k] || 0} ${k}`)
            .join(" · ")}
        </span>
      </div>

      {items.length === 0 ? (
        <div className="text-muted p-6 text-center border border-dashed border-border rounded-lg">
          Nenhuma NF nesta competência.
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-xs text-muted border-b border-border">
            <tr>
              <th className="text-left py-2">Nº</th>
              <th className="text-left py-2">Tomador</th>
              <th className="text-right py-2">Valor</th>
              <th className="text-right py-2">Líquido</th>
              <th className="text-left py-2">Status</th>
              <th className="text-left py-2">Contrato</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((n) => {
              const b = statusBadge[n.status_matching] ?? statusBadge.erro;
              return (
                <tr key={n.id} className="border-b border-border/40">
                  <td className="py-2 font-mono text-xs">{n.numero}</td>
                  <td className="py-2">
                    {n.tomador_nome || "—"}{" "}
                    <span className="text-xs text-muted">{n.tomador_doc}</span>
                  </td>
                  <td className="py-2 text-right">{brl(n.valor_servicos)}</td>
                  <td className="py-2 text-right">{brl(n.valor_liquido)}</td>
                  <td className="py-2">
                    <span className={`px-2 py-0.5 rounded text-xs ${b.cls}`}>{b.label}</span>
                  </td>
                  <td className="py-2 text-xs">{n.contract_id?.slice(0, 8) || "—"}</td>
                  <td className="py-2 text-right">
                    {(n.status_matching === "pendente" || n.status_matching === "sem_match") && (
                      <button
                        onClick={() => setEditing(n)}
                        className="px-2 py-1 text-xs bg-primary-dark text-white rounded hover:opacity-90"
                      >
                        Vincular
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {editing && (
        <VincularModal
          nfse={editing}
          onClose={() => setEditing(null)}
          onDone={() => { setEditing(null); refresh(); }}
        />
      )}
    </div>
  );
}
