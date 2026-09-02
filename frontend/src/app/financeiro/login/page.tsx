"use client";

import { useEffect, useState } from "react";
import Logo from "@/components/ui/Logo";

export default function FinanceiroLoginPage() {
  const [csrfToken, setCsrfToken] = useState("");

  useEffect(() => {
    fetch("/api/auth/csrf")
      .then((r) => r.json())
      .then((d) => setCsrfToken(d.csrfToken));
  }, []);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-6">
            <Logo variant="dark" className="h-12 w-auto" />
          </div>
          <h1 className="font-display text-xl font-semibold text-primary-dark tracking-wide">
            Setor Financeiro
          </h1>
          <p className="text-sm text-muted mt-2">
            Acesso restrito. Use sua conta Microsoft do escritório.
          </p>
        </div>

        <form action="/api/auth/signin/microsoft-entra-id" method="POST">
          <input type="hidden" name="csrfToken" value={csrfToken} />
          <input type="hidden" name="callbackUrl" value="/financeiro" />
          <button
            type="submit"
            className="w-full flex items-center justify-center gap-3 px-6 py-3 bg-primary-dark text-white rounded-lg font-medium hover:bg-primary-dark/90 transition shadow-sm"
          >
            <svg className="w-5 h-5" viewBox="0 0 21 21" fill="none">
              <rect x="1" y="1" width="9" height="9" fill="#F25022" />
              <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
              <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
              <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
            </svg>
            Entrar no Financeiro
          </button>
        </form>

        {process.env.NEXT_PUBLIC_DEV_MODE === "true" && (
          <a
            href="/financeiro/dev-login"
            className="block mt-3 text-center text-xs text-warning hover:underline"
          >
            [DEV] Entrar como usuário de teste
          </a>
        )}

        <div className="mt-8 text-xs text-muted bg-card border border-border rounded-lg p-4 space-y-2">
          <p className="font-medium text-foreground">Acesso autorizado a:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>Usuários com perfil <strong>financeiro</strong></li>
            <li>Administradores</li>
          </ul>
          <p className="pt-2 border-t border-border/60">
            Se sua conta não tem permissão, solicite ao administrador via página
            <a href="/admin" className="text-accent hover:underline"> /admin</a>.
          </p>
        </div>
      </div>
    </div>
  );
}
