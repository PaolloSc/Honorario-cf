"use client";

import { signIn } from "next-auth/react";
import { useState } from "react";
import Logo from "@/components/ui/Logo";

export default function LoginForm({ callbackUrl }: { callbackUrl: string }) {
  const [pending, setPending] = useState(false);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-6">
            <Logo variant="dark" format="vertical" className="h-24 w-auto" />
          </div>
          <h1 className="font-display text-xl font-semibold text-primary-dark tracking-wide">
            C&amp;F Advogados
          </h1>
          <p className="text-sm text-muted mt-2">
            Faça login com sua conta Microsoft do escritório.
          </p>
        </div>

        <button
          type="button"
          disabled={pending}
          onClick={() => {
            setPending(true);
            signIn("microsoft-entra-id", { callbackUrl });
          }}
          className="w-full flex items-center justify-center gap-3 px-6 py-3 bg-primary-dark text-white rounded-lg font-medium hover:bg-primary-dark/90 transition shadow-sm disabled:opacity-60"
        >
          <svg className="w-5 h-5" viewBox="0 0 21 21" fill="none">
            <rect x="1" y="1" width="9" height="9" fill="#F25022" />
            <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
            <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
            <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
          </svg>
          {pending ? "Redirecionando…" : "Entrar com Microsoft"}
        </button>

        <p className="text-xs text-muted text-center mt-6">
          Acesso restrito ao Carvalho &amp; Furtado Advogados.
        </p>
      </div>
    </div>
  );
}
