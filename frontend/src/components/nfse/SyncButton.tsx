"use client";

import { useState } from "react";
import { nfseApi } from "@/app/lib/nfse-api";

export function SyncButton({ cnpj }: { cnpj: string }) {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={async () => {
          setLoading(true);
          setMsg("");
          try {
            const r = await nfseApi.syncManual(cnpj);
            setMsg(r.msg);
          } catch (e) {
            setMsg(e instanceof Error ? e.message : "erro");
          } finally {
            setLoading(false);
          }
        }}
        disabled={loading || !cnpj}
        title="Pede ao robô para trazer do portal da prefeitura as notas novas deste CNPJ. Pode levar alguns minutos."
        className="px-3 py-1.5 text-xs bg-primary-dark text-white rounded font-medium disabled:opacity-50"
      >
        {loading ? "Pedindo a busca..." : "Buscar notas agora"}
      </button>
      {msg && <span className="text-xs text-muted">{msg}</span>}
    </div>
  );
}
