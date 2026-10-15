"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { fetchAutenticado, SessaoExpiradaError } from "@/app/lib/api";
import { AbaEmissor } from "@/components/emissao/AbaEmissor";
import { AbaFaturas } from "@/components/emissao/AbaFaturas";
import { AbaNotas } from "@/components/emissao/AbaNotas";
import { AbaServicos } from "@/components/emissao/AbaServicos";
import { AbaTomadores } from "@/components/emissao/AbaTomadores";

const ABAS = [
  { id: "faturas", rotulo: "Faturas" },
  { id: "notas", rotulo: "Notas emitidas" },
  { id: "servicos", rotulo: "Serviços" },
  { id: "tomadores", rotulo: "Tomadores" },
  { id: "emissor", rotulo: "Emissor" },
] as const;
type AbaId = (typeof ABAS)[number]["id"];

export default function EmissaoPage() {
  const { data: session, status } = useSession();
  const [aba, setAba] = useState<AbaId>("faturas");
  const [role, setRole] = useState<string | null>(null);
  const [erro, setErro] = useState("");

  const token = session?.accessToken;
  const devMode = typeof window !== "undefined" && process.env.NEXT_PUBLIC_DEV_MODE === "true";
  const hasDevSession = typeof window !== "undefined" && !!localStorage.getItem("dev_user_email");

  useEffect(() => {
    if (!token && !(devMode && hasDevSession)) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
      (typeof window !== "undefined" ? `${window.location.protocol}//${window.location.hostname}` : "");
    fetchAutenticado(`${apiBase}/api/users/me`)
      .then((r) => {
        if (r.status === 401) {
          window.location.href = "/financeiro/login";
          return null;
        }
        return r.json();
      })
      .then((u) => u && setRole(u.role))
      .catch((e) => {
        if (e instanceof SessaoExpiradaError) window.location.href = "/financeiro/login";
        else setErro("Falha ao verificar perfil");
      });
  }, [token, devMode, hasDevSession]);

  if (status === "loading") return <div className="p-8 text-muted">Carregando sessão...</div>;
  if (role && role !== "financeiro" && role !== "admin") {
    return (
      <div className="max-w-xl mx-auto mt-16 p-8 bg-danger/[0.08] border border-danger rounded-lg text-center">
        <h2 className="text-lg font-semibold text-danger mb-2">Acesso Restrito</h2>
        <p className="text-danger">Esta página é exclusiva do setor financeiro.</p>
        <a href="/" className="mt-4 inline-block text-sm text-primary hover:underline">Voltar</a>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <header className="mb-6">
        <a href="/financeiro" className="text-sm text-primary hover:underline">← Setor Financeiro</a>
        <h1 className="font-display text-2xl font-semibold text-primary-dark tracking-wide mt-2">Emissão de NFS-e</h1>
        <p className="text-sm text-muted mt-1">Faturas, notas emitidas e cadastros. Ambiente de homologação: sem valor fiscal.</p>
      </header>
      {erro && <div className="mb-4 rounded-lg border border-danger bg-danger/[0.08] p-3 text-sm text-danger">{erro}</div>}

      <nav aria-label="Seções da emissão" className="flex gap-2 mb-4 border-b border-border overflow-x-auto">
        {ABAS.map((a) => (
          <button key={a.id} onClick={() => setAba(a.id)} aria-current={aba === a.id ? "page" : undefined}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition shrink-0 whitespace-nowrap ${
              aba === a.id ? "border-primary-dark text-primary-dark" : "border-transparent text-muted hover:text-foreground"
            }`}>
            {a.rotulo}
          </button>
        ))}
      </nav>

      {role && (
        <>
          {aba === "faturas" && <AbaFaturas />}
          {aba === "notas" && <AbaNotas />}
          {aba === "servicos" && <AbaServicos />}
          {aba === "tomadores" && <AbaTomadores />}
          {aba === "emissor" && <AbaEmissor />}
        </>
      )}
    </div>
  );
}
