"use client";

import { useState } from "react";
import type { ItemClausula } from "@/app/lib/api";

interface Props {
  itens: ItemClausula[];
  descartados: string[];
  salvando: boolean;
  onSalvar: (item: ItemClausula, texto: string) => void;
  onVoltar: (item: ItemClausula) => void;
  onIrParaEtapa: (etapa: number) => void;
}

const ETAPA_NOME: Record<number, string> = { 3: "Honorários", 4: "Acessórios" };

// Painel "Ajustar texto": edita uma cláusula por vez; numeração, títulos, partes e
// assinaturas continuam sob controle do gerador.
export default function AjustarTexto({ itens, descartados, salvando, onSalvar, onVoltar, onIrParaEtapa }: Props) {
  const [editando, setEditando] = useState<string | null>(null);
  const [rascunho, setRascunho] = useState("");
  const ajustados = itens.filter((i) => i.ajustado).length;

  return (
    <details className="border border-border rounded-xl bg-card" open={ajustados > 0 || undefined}>
      <summary className="cursor-pointer px-4 py-3 font-medium flex items-center gap-2 flex-wrap">
        Ajustar texto
        {ajustados > 0 && (
          <span className="text-[11px] font-medium text-warning bg-warning/[0.16] border border-warning rounded-full px-2 py-0.5">
            {ajustados} ajustado{ajustados > 1 ? "s" : ""} à mão
          </span>
        )}
      </summary>
      <div className="px-4 pb-4 space-y-3">
        <p className="text-sm text-muted">
          Edite o texto de uma cláusula. Numeração, títulos, qualificação das partes e assinaturas seguem o padrão do contrato.
        </p>
        {descartados.length > 0 && (
          <p className="text-sm text-warning bg-warning/[0.1] border border-warning rounded-lg p-3">
            {descartados.length === 1 ? "Uma cláusula ajustada deixou" : `${descartados.length} cláusulas ajustadas deixaram`} de
            existir após mudanças nas etapas anteriores e {descartados.length === 1 ? "o ajuste foi descartado" : "os ajustes foram descartados"} ({descartados.join(", ")}).
          </p>
        )}
        <ul className="divide-y divide-border">
          {itens.map((item, idx) => {
            const novaSecao = idx === 0 || itens[idx - 1].clausula !== item.clausula;
            return (
              <li key={item.id} className="py-2">
                {novaSecao && <p className="text-xs font-semibold text-muted uppercase tracking-wide mb-1.5">{item.clausula}</p>}
                {editando === item.id ? (
                  <div className="space-y-2">
                    <textarea
                      value={rascunho}
                      onChange={(e) => setRascunho(e.target.value)}
                      rows={6}
                      aria-label={`Texto da cláusula ${item.id}`}
                      className="w-full px-3 py-2 border border-border bg-card text-foreground rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                    />
                    <div className="flex gap-2 flex-wrap">
                      <button
                        type="button"
                        disabled={salvando || !rascunho.trim()}
                        onClick={() => {
                          onSalvar(item, rascunho);
                          setEditando(null);
                        }}
                        className="px-3 py-1.5 rounded-lg bg-primary text-white text-sm disabled:opacity-50"
                      >
                        Salvar
                      </button>
                      <button type="button" onClick={() => setEditando(null)} className="px-3 py-1.5 rounded-lg border border-border text-sm">
                        Cancelar
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex gap-3 items-start">
                    <p className={`flex-1 text-sm ${item.ajustado ? "bg-warning/[0.12] border-l-2 border-warning pl-2" : ""}`}>
                      <span className="font-medium">{item.id}.</span> {item.texto}
                      {item.ajustado && <span className="ml-2 text-[11px] font-medium text-warning">Ajustado à mão</span>}
                      {item.status === "padrao_mudou" && (
                        <span className="block text-xs text-warning mt-1">
                          O texto padrão deste item mudou, revise seu ajuste.
                        </span>
                      )}
                    </p>
                    <div className="shrink-0 flex flex-col gap-1 items-end text-sm">
                      {item.editavel ? (
                        <>
                          <button
                            type="button"
                            className="text-primary-dark underline"
                            onClick={() => {
                              setEditando(item.id);
                              setRascunho(item.texto);
                            }}
                          >
                            Editar
                          </button>
                          {item.ajustado && (
                            <button type="button" disabled={salvando} className="text-muted underline" onClick={() => onVoltar(item)}>
                              Voltar ao texto padrão
                            </button>
                          )}
                        </>
                      ) : (
                        <button type="button" className="text-muted underline" onClick={() => item.etapa && onIrParaEtapa(item.etapa)}>
                          Altere na etapa {item.etapa}
                          {item.etapa && ETAPA_NOME[item.etapa] ? ` (${ETAPA_NOME[item.etapa]})` : ""}
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </details>
  );
}
