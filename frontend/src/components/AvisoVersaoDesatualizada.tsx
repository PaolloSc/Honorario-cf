"use client";

import { useEffect, useState } from "react";
import { adotarVersaoAtual, EVENTO_VERSAO_DESATUALIZADA } from "@/app/lib/api";

interface Aviso { motivo: string; contractId: string; versaoAtual?: number }

/** Aba velha tentou salvar: avisa e deixa a pessoa escolher quando recarregar (o digitado não se perde). */
export default function AvisoVersaoDesatualizada() {
  const [aviso, setAviso] = useState<Aviso | null>(null);
  useEffect(() => {
    const ouvir = (e: Event) => setAviso((e as CustomEvent).detail as Aviso);
    window.addEventListener(EVENTO_VERSAO_DESATUALIZADA, ouvir);
    return () => window.removeEventListener(EVENTO_VERSAO_DESATUALIZADA, ouvir);
  }, []);
  if (!aviso) return null;
  const motivo = aviso.motivo || "Este contrato foi alterado em outra aba.";
  const salvarSobreAtual = () => {
    if (aviso.versaoAtual == null) return;
    if (!window.confirm("Salvar sobre a versão atual substitui o que a outra aba gravou pelo que está nesta tela. Confirmar?")) return;
    adotarVersaoAtual(aviso.contractId, aviso.versaoAtual);
    setAviso(null);
  };
  return (
    <div role="alert" className="fixed bottom-4 left-4 right-4 sm:left-auto sm:max-w-md z-50 rounded-lg border border-warning bg-card p-4 text-sm shadow-lg">
      <p className="text-foreground">{motivo} Nada foi salvo. Recarregue para ver a versão atual ou, se o que está nesta tela deve prevalecer, salve sobre a versão atual e clique em Salvar de novo.</p>
      <div className="mt-3 flex flex-wrap gap-3">
        <button type="button" onClick={() => window.location.reload()} className="px-4 py-2 bg-primary text-white rounded-lg font-medium hover:bg-primary-dark transition">Recarregar</button>
        {aviso.versaoAtual != null && (
          <button type="button" onClick={salvarSobreAtual} className="px-4 py-2 border border-danger/40 text-danger rounded-lg font-medium hover:bg-danger/10 transition">Salvar sobre a versão atual</button>
        )}
        <button type="button" onClick={() => setAviso(null)} className="px-4 py-2 text-muted underline">Fechar</button>
      </div>
    </div>
  );
}
