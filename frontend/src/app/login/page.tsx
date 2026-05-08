"use client";

import { useEffect, useState } from "react";
import Logo from "@/components/ui/Logo";

export default function LoginPage() {
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
            Sistema de Honorarios
          </h1>
          <p className="text-sm text-muted mt-2">
            Faca login com sua conta Microsoft do escritorio.
          </p>
        </div>

        <form action="/api/auth/signin/microsoft-entra-id" method="POST">
          <input type="hidden" name="csrfToken" value={csrfToken} />
          <input type="hidden" name="callbackUrl" value="/" />
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
            Entrar com Microsoft
          </button>
        </form>

        <p className="text-xs text-muted text-center mt-6">
          Acesso restrito a advogados de Carvalho &amp; Furtado.
        </p>
      </div>
    </div>
  );
}
