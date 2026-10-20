"use client";

import type { DocumentoDerivado } from "@/app/lib/api";
import { formatarDataHora } from "@/app/lib/datas";
import { TipoBadge } from "./Selos";

const STATUS: Record<string, string> = {
  rascunho: "Rascunho",
  enviado: "Enviado p/ assinatura",
  assinado: "Assinado",
  cancelado: "Cancelado",
  recusado: "Recusado",
  encerrado: "Encerrado",
};

/** Seção "Documentos" do contrato de origem: aditivos, distrato e substabelecimentos. */
export default function DocumentosDerivados({ documentos }: { documentos: DocumentoDerivado[] }) {
  if (documentos.length === 0) return null;
  return (
    <div className="bg-card rounded-xl border border-border p-5 mb-8">
      <h3 className="font-display text-sm font-semibold text-primary-dark mb-3">Documentos ({documentos.length})</h3>
      <ul className="divide-y divide-border/60">
        {documentos.map((d) => (
          <li key={d.contract_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
            <TipoBadge tipo={d.tipo_contrato} />
            <span className="text-muted">{STATUS[d.status] ?? d.status}</span>
            <span className="text-xs text-muted">{formatarDataHora(d.created_at)}</span>
            <a href={`/contracts/${d.contract_id}`} className="ml-auto text-primary font-medium hover:underline">Abrir</a>
          </li>
        ))}
      </ul>
    </div>
  );
}
