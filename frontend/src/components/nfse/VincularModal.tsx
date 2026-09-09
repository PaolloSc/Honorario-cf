"use client";

import { useState } from "react";
import { nfseApi, type NFSeOut } from "@/app/lib/nfse-api";

export function VincularModal({
  nfse, onClose, onDone,
}: { nfse: NFSeOut; onClose: () => void; onDone: () => void }) {
  const [contractId, setContractId] = useState("");
  const [motivo, setMotivo] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      await nfseApi.vincular(nfse.id, { contract_id: contractId, motivo: motivo || undefined });
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "erro");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <form onSubmit={submit}
            className="bg-card border border-border rounded-lg p-6 max-w-md w-full space-y-3 text-sm">
        <div className="flex justify-between items-center">
          <h3 className="font-medium">Vincular NF #{nfse.numero}</h3>
          <button type="button" onClick={onClose} className="text-muted">✕</button>
        </div>
        <p className="text-xs text-muted">
          Tomador: {nfse.tomador_nome} ({nfse.tomador_doc}) — competência {nfse.competencia}
        </p>
        <label className="block">
          <span className="text-xs text-muted">ID do contrato *</span>
          <input
            required value={contractId}
            onChange={(e) => setContractId(e.target.value)}
            className="w-full px-3 py-2 border border-border rounded"
          />
        </label>
        <label className="block">
          <span className="text-xs text-muted">Motivo</span>
          <input
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            className="w-full px-3 py-2 border border-border rounded"
          />
        </label>
        {err && <div className="text-xs text-danger">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose}
                  className="px-3 py-1.5 border border-border rounded text-xs">Cancelar</button>
          <button type="submit" disabled={saving}
                  className="px-3 py-1.5 bg-primary-dark text-white rounded text-xs disabled:opacity-50">
            {saving ? "Vinculando..." : "Confirmar"}
          </button>
        </div>
      </form>
    </div>
  );
}
