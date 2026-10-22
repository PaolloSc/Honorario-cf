"use client";

import { useEffect, useState } from "react";
import { EVENTO_VERSAO_DESATUALIZADA } from "@/app/lib/api";

/** Aba velha tentou salvar: avisa e deixa a pessoa escolher quando recarregar (o digitado não se perde). */
export default function AvisoVersaoDesatualizada() {
  const [motivo, setMotivo] = useState<string | null>(null);
  useEffect(() => {
    const ouvir = (e: Event) => setMotivo(String((e as CustomEvent).detail || "Este contrato foi alterado em outra aba."));
    window.addEventListener(EVENTO_VERSAO_DESATUALIZADA, ouvir);
    return () => window.removeEventListener(EVENTO_VERSAO_DESATUALIZADA, ouvir);
  }, []);
  if (!motivo) return null;
  return (
    <div role="alert" className="fixed bottom-4 left-4 right-4 sm:left-auto sm:max-w-md z-50 rounded-lg border border-warning bg-card p-4 text-sm shadow-lg">
      <p className="text-foreground">{motivo} Nada foi salvo. Copie o que digitou, se precisar, e recarregue para ver a versão atual.</p>
      <div className="mt-3 flex gap-3">
        <button type="button" onClick={() => window.location.reload()} className="px-4 py-2 bg-primary text-white rounded-lg font-medium hover:bg-primary-dark transition">Recarregar</button>
        <button type="button" onClick={() => setMotivo(null)} className="px-4 py-2 text-muted underline">Continuar aqui</button>
      </div>
    </div>
  );
}
