"use client";

/**
 * Login de DESENVOLVIMENTO — apenas para testar a plataforma localmente
 * sem precisar de conta Microsoft. Requer:
 *   - backend: DEV_MODE=true (.env)
 *   - frontend: NEXT_PUBLIC_DEV_MODE=true (.env.local)
 *
 * NÃO usar em produção.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const USUARIOS = [
  { email: "financeiro@teste.local", nome: "Financeiro Teste", role: "financeiro" },
  { email: "admin@teste.local", nome: "Admin Teste", role: "admin" },
  { email: "advogado@teste.local", nome: "Advogado Teste", role: "advogado" },
];

export default function DevLoginPage() {
  const router = useRouter();
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    setEnabled(process.env.NEXT_PUBLIC_DEV_MODE === "true");
  }, []);

  const login = (email: string, role: string, nome: string) => {
    localStorage.setItem("dev_user_email", email);
    localStorage.setItem("dev_user_role", role);
    localStorage.setItem("dev_user_name", nome);
    document.cookie = `dev_session=${encodeURIComponent(email)}; path=/; max-age=86400`;
    if (role === "admin") router.push("/admin");
    else if (role === "financeiro") router.push("/financeiro");
    else router.push("/");
  };

  if (!enabled) {
    return (
      <div className="max-w-md mx-auto mt-20 p-8 bg-danger/[0.08] border border-danger rounded-lg text-center">
        <h2 className="font-semibold text-danger">Modo dev desativado</h2>
        <p className="text-sm text-danger mt-2">
          Defina <code>NEXT_PUBLIC_DEV_MODE=true</code> em <code>.env.local</code> e reinicie o frontend.
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        <h1 className="font-display text-xl font-semibold text-primary-dark text-center mb-2">
          Login de Desenvolvimento
        </h1>
        <p className="text-xs text-muted text-center mb-6">
          Selecione um usuário de teste. Requer{" "}
          <code className="bg-border/35 px-1 rounded">DEV_MODE=true</code> no backend e seed rodado.
        </p>

        <div className="space-y-2">
          {USUARIOS.map((u) => (
            <button
              key={u.email}
              onClick={() => login(u.email, u.role, u.nome)}
              className="w-full text-left p-4 bg-card border border-border rounded-lg hover:border-primary-dark transition"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-foreground">{u.nome}</div>
                  <div className="text-xs text-muted">{u.email}</div>
                </div>
                <span
                  className={`text-xs px-2 py-1 rounded-full ${
                    u.role === "admin"
                      ? "bg-accent/[0.16] text-accent"
                      : u.role === "financeiro"
                      ? "bg-primary/[0.16] text-primary-dark"
                      : "bg-warning/[0.16] text-warning"
                  }`}
                >
                  {u.role}
                </span>
              </div>
            </button>
          ))}
        </div>

        <p className="text-xs text-muted text-center mt-6">
          Antes de usar:{" "}
          <code className="bg-border/35 px-1 rounded">python backend/seed_test_users.py</code>
        </p>
      </div>
    </div>
  );
}
