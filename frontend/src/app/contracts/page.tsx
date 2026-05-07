"use client";

import {
  listContracts,
  type ContractSummary,
  type ContractListResponse,
} from "@/app/lib/api";
import { useCallback, useEffect, useState } from "react";

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  rascunho: { label: "Rascunho", color: "bg-gray-100 text-gray-700" },
  enviado: { label: "Enviado p/ Assinatura", color: "bg-amber-100 text-amber-800" },
  assinado: { label: "Assinado", color: "bg-green-100 text-green-800" },
  cancelado: { label: "Cancelado", color: "bg-red-100 text-red-800" },
};

function StatusBadge({ status }: { status: string }) {
  const info = STATUS_LABELS[status] || { label: status, color: "bg-gray-100 text-gray-700" };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${info.color}`}>
      {info.label}
    </span>
  );
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ContractsPage() {
  const [data, setData] = useState<ContractListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);

  const fetchContracts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await listContracts({
        page,
        page_size: 20,
        status: statusFilter || undefined,
        search: search || undefined,
      });
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar contratos");
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, search]);

  useEffect(() => {
    fetchContracts();
  }, [fetchContracts]);

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="font-display text-2xl font-semibold text-primary-dark tracking-wide">
            Contratos
          </h1>
          <p className="text-sm text-muted mt-1">
            {data ? `${data.total} contrato${data.total !== 1 ? "s" : ""}` : "Carregando..."}
          </p>
        </div>
        <a
          href="/"
          className="px-5 py-2.5 bg-primary text-white rounded-lg font-medium hover:bg-primary-dark transition text-sm"
        >
          + Novo Contrato
        </a>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <input
          type="text"
          placeholder="Buscar por nome, email ou ID..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="flex-1 px-4 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="px-4 py-2 border border-border rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">Todos os status</option>
          <option value="rascunho">Rascunho</option>
          <option value="enviado">Enviado p/ Assinatura</option>
          <option value="assinado">Assinado</option>
          <option value="cancelado">Cancelado</option>
        </select>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-gray-50/50">
                <th className="text-left px-4 py-3 font-medium text-muted">Cliente</th>
                <th className="text-left px-4 py-3 font-medium text-muted">Status</th>
                <th className="text-left px-4 py-3 font-medium text-muted hidden md:table-cell">Versao</th>
                <th className="text-left px-4 py-3 font-medium text-muted hidden md:table-cell">Criado</th>
                <th className="text-left px-4 py-3 font-medium text-muted hidden lg:table-cell">Atualizado</th>
                <th className="text-right px-4 py-3 font-medium text-muted">Acoes</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-muted">
                    Carregando...
                  </td>
                </tr>
              )}
              {!loading && data?.contracts.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-muted">
                    Nenhum contrato encontrado.
                  </td>
                </tr>
              )}
              {!loading &&
                data?.contracts.map((c: ContractSummary) => (
                  <tr key={c.contract_id} className="border-b border-border/50 hover:bg-gray-50/50 transition">
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium text-foreground">{c.client_name || "—"}</p>
                        <p className="text-xs text-muted">{c.client_email || c.contract_id.slice(0, 8)}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell text-muted">v{c.current_version}</td>
                    <td className="px-4 py-3 hidden md:table-cell text-muted">{formatDate(c.created_at)}</td>
                    <td className="px-4 py-3 hidden lg:table-cell text-muted">{formatDate(c.updated_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <a
                          href={`/contracts/${c.contract_id}`}
                          className="px-3 py-1.5 text-xs font-medium text-primary border border-primary/30 rounded-md hover:bg-primary/5 transition"
                        >
                          Ver
                        </a>
                        <a
                          href={`/contracts/${c.contract_id}/edit`}
                          className="px-3 py-1.5 text-xs font-medium text-accent border border-accent/30 rounded-md hover:bg-accent/5 transition"
                        >
                          Editar
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 text-xs border border-border rounded-md disabled:opacity-30"
            >
              Anterior
            </button>
            <span className="text-xs text-muted">
              Pagina {page} de {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1.5 text-xs border border-border rounded-md disabled:opacity-30"
            >
              Proxima
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
