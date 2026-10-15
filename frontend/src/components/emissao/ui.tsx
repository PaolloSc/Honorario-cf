"use client";

import { useEffect, useRef } from "react";
import { CLASSE_STATUS, ROTULO_STATUS, type StatusFatura, type StatusNota } from "@/app/lib/emissao";

/** Selo de situação: sempre texto (a cor só reforça), com indicador no "processando". */
export function StatusBadge({ status }: { status: StatusFatura | StatusNota }) {
  const andando = status === "processando" || status === "emitindo";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${CLASSE_STATUS[status]}`}>
      {andando && <span aria-hidden className="inline-block mr-1 animate-pulse">●</span>}
      {ROTULO_STATUS[status]}
    </span>
  );
}

export function Aviso({ tipo, children }: { tipo: "ok" | "erro" | "aviso"; children: React.ReactNode }) {
  const cls =
    tipo === "ok"
      ? "border-success bg-success/[0.08] text-success"
      : tipo === "erro"
        ? "border-danger bg-danger/[0.08] text-danger"
        : "border-warning bg-warning/[0.08] text-warning";
  return (
    <div role={tipo === "erro" ? "alert" : "status"} className={`mb-4 rounded-lg border p-3 text-sm ${cls}`}>
      {children}
    </div>
  );
}

export const inputCls =
  "w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary-light focus:border-primary-light";
export const botaoPrimario =
  "px-5 py-2.5 rounded-lg bg-primary-dark text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed";
export const botaoSecundario =
  "px-4 py-2 rounded-lg border border-border text-sm text-foreground hover:bg-border/20 disabled:opacity-50";

export function Campo({ rotulo, dica, children }: { rotulo: string; dica?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-sm font-semibold text-foreground mb-1">{rotulo}</span>
      {children}
      {dica && <span className="block text-xs text-muted mt-1">{dica}</span>}
    </label>
  );
}

/** Confirmação de ato sem volta (emitir nota). O foco inicial fica em Cancelar. */
export function ConfirmDialog({
  titulo, texto, verbo, ocupado, onConfirmar, onCancelar,
}: {
  titulo: string;
  texto: React.ReactNode;
  verbo: string;
  ocupado?: boolean;
  onConfirmar: () => void;
  onCancelar: () => void;
}) {
  const cancelar = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    cancelar.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && !ocupado && onCancelar();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onCancelar, ocupado]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div role="dialog" aria-modal="true" aria-labelledby="dlg-titulo" className="w-full max-w-md rounded-lg border border-border bg-card p-6">
        <h2 id="dlg-titulo" className="font-display text-lg font-semibold text-primary-dark mb-2">{titulo}</h2>
        <div className="text-sm text-foreground mb-5">{texto}</div>
        <div className="flex justify-end gap-2">
          <button ref={cancelar} onClick={onCancelar} disabled={ocupado} className={botaoSecundario}>Cancelar</button>
          <button onClick={onConfirmar} disabled={ocupado} className={botaoPrimario}>
            {ocupado ? "Enviando…" : verbo}
          </button>
        </div>
      </div>
    </div>
  );
}
