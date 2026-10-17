"use client";

import { useEffect, useRef, useState } from "react";
import { ROTULO_TIPO, TIPOS_DOCUMENTO, type TipoDocumento } from "@/app/lib/documentos";

/** Único ponto de entrada na página do contrato: Aditivo / Distrato / Substabelecimento. */
export default function NovoDocumentoMenu({
  contratoId,
  distratoExistente,
}: {
  contratoId: string;
  distratoExistente: boolean;
}) {
  const [aberto, setAberto] = useState(false);
  const raiz = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => !raiz.current?.contains(e.target as Node) && setAberto(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setAberto(false);
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [aberto]);

  const dica: Partial<Record<TipoDocumento, string>> = {
    aditivo: "Altera objeto, remuneração ou abrangência",
    distrato: distratoExistente ? "Este contrato já tem um distrato" : "Encerra o contrato",
    substabelecimento: "Transfere poderes em processos",
  };

  return (
    <div ref={raiz} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={aberto}
        onClick={() => setAberto((v) => !v)}
        className="px-5 py-2.5 border border-primary text-primary rounded-lg text-sm font-medium hover:bg-primary/5 transition"
      >
        Novo documento ▾
      </button>
      {aberto && (
        <div role="menu" className="absolute left-0 z-20 mt-1 w-72 max-w-[calc(100vw-2rem)] rounded-lg border border-border bg-card shadow-lg p-1">
          {TIPOS_DOCUMENTO.map((t) => {
            const desabilitado = t === "distrato" && distratoExistente;
            return desabilitado ? (
              <div key={t} role="menuitem" aria-disabled="true" className="px-3 py-2 rounded text-sm text-muted opacity-60 cursor-not-allowed">
                <span className="font-medium block">{ROTULO_TIPO[t]}</span>
                <span className="text-xs">{dica[t]}</span>
              </div>
            ) : (
              <a
                key={t}
                role="menuitem"
                href={`/documentos/novo?tipo=${t}&origem=${contratoId}`}
                className="block px-3 py-2 rounded text-sm text-foreground hover:bg-background"
              >
                <span className="font-medium block">{ROTULO_TIPO[t]}</span>
                <span className="text-xs text-muted">{dica[t]}</span>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
