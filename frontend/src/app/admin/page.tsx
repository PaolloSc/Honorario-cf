"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";

interface User {
  id: number;
  azure_id: string;
  email: string;
  name: string;
  role: string;
  created_at: string;
}

// A descricao e' o que faltava: com "Legal One" sozinho ninguem adivinha que e'
// ali que se cadastram as etiquetas.
const CADASTROS = [
  {
    href: "/admin/colaboradores",
    titulo: "Colaboradores",
    descricao: "Advogados e sócios oferecidos nas listas suspensas do contrato.",
  },
  {
    href: "/admin/legalone",
    titulo: "Legal One",
    descricao: "Categorias de cliente, etiquetas e listas de transmissão da ficha do financeiro.",
  },
];

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  (typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}`
    : "http://127.0.0.1:8000");

export default function AdminPage() {
  const { data: session } = useSession();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [accessDenied, setAccessDenied] = useState(false);

  const token = session?.accessToken;

  const fetchUsers = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/users`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 403) {
        setAccessDenied(true);
        setError("Acesso restrito a administradores.");
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setUsers(data.users);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar usuarios");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const setRole = async (userId: number, newRole: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/users/${userId}/role`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ role: newRole }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      fetchUsers();
    } catch {
      alert("Erro ao alterar permissao");
    }
  };

  if (accessDenied) {
    return (
      <div className="max-w-xl mx-auto mt-16 p-8 bg-red-50 border border-red-200 rounded-lg text-center">
        <h2 className="text-lg font-semibold text-red-900 mb-2">Acesso Restrito</h2>
        <p className="text-red-700">Você não tem permissão para acessar esta página.</p>
        <a href="/" className="mt-4 inline-block text-sm text-primary hover:underline">
          Voltar ao inicio
        </a>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="font-display text-2xl font-semibold text-primary-dark tracking-wide mb-2">
        Administracao
      </h1>
      <p className="text-sm text-muted mb-4">
        Gerencie usuarios e permissoes do sistema.
      </p>

      <h2 className="text-sm font-semibold text-foreground mb-3">Cadastros</h2>
      <nav aria-label="Cadastros" className="grid gap-3 sm:grid-cols-2 mb-8">
        {CADASTROS.map((c) => (
          <a
            key={c.href}
            href={c.href}
            className="group flex items-start gap-3 rounded-xl border border-border bg-card p-4 shadow-sm transition hover:border-primary hover:shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          >
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium text-foreground group-hover:text-primary">
                {c.titulo}
              </span>
              <span className="mt-0.5 block text-xs text-muted">{c.descricao}</span>
            </span>
            <svg
              aria-hidden="true"
              viewBox="0 0 20 20"
              fill="none"
              className="mt-0.5 h-4 w-4 shrink-0 text-muted transition group-hover:translate-x-0.5 group-hover:text-primary"
            >
              <path
                d="M7.5 4.5 13 10l-5.5 5.5"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </a>
        ))}
      </nav>

      <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-border bg-gray-50/50">
          <h2 className="font-medium text-sm text-foreground">
            Usuarios ({users.length})
          </h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left px-4 py-3 font-medium text-muted">Nome</th>
              <th className="text-left px-4 py-3 font-medium text-muted">E-mail</th>
              <th className="text-left px-4 py-3 font-medium text-muted">Perfil</th>
              <th className="text-right px-4 py-3 font-medium text-muted">Acoes</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-muted">
                  Carregando...
                </td>
              </tr>
            )}
            {!loading &&
              users.map((u) => (
                <tr key={u.id} className="border-b border-border/50 hover:bg-gray-50/50">
                  <td className="px-4 py-3 font-medium">{u.name}</td>
                  <td className="px-4 py-3 text-muted">{u.email}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        u.role === "admin"
                          ? "bg-purple-100 text-purple-800"
                          : u.role === "financeiro"
                          ? "bg-emerald-100 text-emerald-800"
                          : u.role === "leitor"
                          ? "bg-gray-100 text-gray-700"
                          : "bg-blue-100 text-blue-800"
                      }`}
                    >
                      {u.role === "admin"
                        ? "Administrador"
                        : u.role === "financeiro"
                        ? "Financeiro"
                        : u.role === "leitor"
                        ? "Leitor (somente leitura)"
                        : "Advogado"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <select
                      value={u.role}
                      onChange={(e) => setRole(u.id, e.target.value)}
                      className="text-xs border border-border rounded px-2 py-1"
                    >
                      <option value="advogado">Advogado</option>
                      <option value="financeiro">Financeiro</option>
                      <option value="admin">Admin</option>
                      <option value="leitor">Leitor (somente leitura)</option>
                    </select>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {error && !accessDenied && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {error}
        </div>
      )}
    </div>
  );
}
