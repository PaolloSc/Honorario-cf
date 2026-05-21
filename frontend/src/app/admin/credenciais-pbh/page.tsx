"use client";

import { CredencialPbhPanel } from "@/components/admin/CredencialPbhForm";

export default function Page() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-primary-dark tracking-wide">
          Credenciais PBH — BHISS Digital
        </h1>
        <p className="text-sm text-muted mt-1">
          Cadastro de login/senha do portal usados pelo worker NFS-e.
        </p>
      </header>
      <CredencialPbhPanel />
    </div>
  );
}
