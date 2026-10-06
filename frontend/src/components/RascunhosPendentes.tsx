"use client";

import { deleteDraft, listDrafts, type DraftSummary } from "@/app/lib/api";
import { formatarDataHora } from "@/app/lib/datas";
import { listarLocais, removerLocal, useDonoRascunho } from "@/app/lib/rascunhoLocal";
import { useAuthStatus } from "@/app/lib/useAuthStatus";
import { useCallback, useEffect, useState } from "react";

interface Item extends DraftSummary {
  soLocal: boolean;
}

const ETAPAS = ["Contratante", "Escopo", "Honorários", "Acessórios", "Ficha Interna", "Revisão", "Envio"];

/**
 * Rascunhos do wizard que a pessoa não terminou. Inclui os que só existem neste
 * navegador (o servidor não respondeu no último salvamento), marcados como tal.
 */
export default function RascunhosPendentes({ titulo = "Rascunhos em andamento" }: { titulo?: string }) {
  const status = useAuthStatus();
  const dono = useDonoRascunho();
  const [itens, setItens] = useState<Item[]>([]);
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    let doServidor: DraftSummary[] = [];
    try {
      doServidor = (await listDrafts()).drafts;
      setErro("");
    } catch {
      setErro("Não foi possível consultar os rascunhos salvos no servidor.");
    }
    const ids = new Set(doServidor.map((d) => d.draft_id));
    const locais: Item[] = listarLocais(dono)
      .filter((l) => !ids.has(l.draft_id))
      .map((l) => ({
        draft_id: l.draft_id,
        client_name: l.client_name,
        current_step: l.current_step,
        created_at: l.updated_at,
        updated_at: l.updated_at,
        soLocal: true,
      }));
    setItens([...doServidor.map((d) => ({ ...d, soLocal: false })), ...locais]);
  }, [dono]);

  useEffect(() => {
    if (status === "authenticated") void carregar();
  }, [status, dono, carregar]);

  const descartar = async (item: Item) => {
    if (!window.confirm(`Descartar o rascunho${item.client_name ? ` de ${item.client_name}` : ""}? Não dá para desfazer.`)) return;
    removerLocal(item.draft_id);
    await deleteDraft(item.draft_id).catch(() => undefined);
    setItens((prev) => prev.filter((i) => i.draft_id !== item.draft_id));
  };

  if (itens.length === 0 && !erro) return null;

  return (
    <div className="mb-6 rounded-xl border border-primary/30 bg-primary/5 p-4">
      <p className="font-semibold text-primary-dark text-sm mb-2">{titulo}</p>
      {erro && <p className="text-xs text-danger mb-2">{erro}</p>}
      <ul className="divide-y divide-border/60">
        {itens.map((item) => (
          <li key={item.draft_id} className="flex flex-wrap items-center justify-between gap-3 py-2">
            <div className="min-w-0">
              <p className="text-sm font-medium text-foreground truncate">
                {item.client_name || "Sem nome de cliente"}
              </p>
              <p className="text-xs text-muted">
                Parou na etapa {item.current_step} ({ETAPAS[item.current_step - 1]}) · {formatarDataHora(item.updated_at)}
                {item.soLocal && " · só neste navegador"}
              </p>
            </div>
            <div className="flex gap-2">
              <a
                href={`/?rascunho=${encodeURIComponent(item.draft_id)}`}
                className="px-3 py-1.5 text-xs font-medium text-white bg-primary rounded-md hover:bg-primary-dark transition"
              >
                Retomar
              </a>
              <button
                type="button"
                onClick={() => void descartar(item)}
                className="px-3 py-1.5 text-xs font-medium text-danger border border-danger/30 rounded-md hover:bg-danger/5 transition"
              >
                Descartar
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
