"use client";

import { useState } from "react";
import type { AjusteDescartado, ItemClausula } from "@/app/lib/api";

interface Props {
  itens: ItemClausula[];
  descartados: AjusteDescartado[];
  salvando: boolean;
  onSalvar: (item: ItemClausula, texto: string) => void;
  onVoltar: (item: ItemClausula) => void;
  onReaplicar: (item: ItemClausula) => void;
  onDescartarSumido: (id: string) => void;
  onIrParaEtapa: (etapa: number) => void;
}

const ETAPA_NOME: Record<number, string> = { 3: "Honorários", 4: "Acessórios" };

// Painel "Ajustar texto": edita uma cláusula por vez; numeração, títulos, partes e
// assinaturas continuam sob controle do gerador.
export default function AjustarTexto({ itens, descartados, salvando, onSalvar, onVoltar, onReaplicar, onDescartarSumido, onIrParaEtapa }: Props) {
  const [editando, setEditando] = useState<string | null>(null);
  const [rascunho, setRascunho] = useState("");
  const [reaplicando, setReaplicando] = useState<string | null>(null);
  const ajustados = itens.filter((i) => i.ajustado || i.status === "padrao_mudou").length;

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
        {descartados.map((d) => (
          <div key={d.id} className="text-sm text-warning bg-warning/[0.1] border border-warning rounded-lg p-3 space-y-2">
            <p>
              Uma cláusula que você ajustou deixou de existir após mudanças nas etapas anteriores. O ajuste não foi aplicado em nenhuma outra
              cláusula. Copie o texto, se quiser aproveitá-lo.
            </p>
            <p className="text-foreground whitespace-pre-wrap border-l-2 border-warning pl-2">{d.texto}</p>
            <div className="flex gap-3">
              <button type="button" className="underline" onClick={() => void navigator.clipboard?.writeText(d.texto)}>
                Copiar texto
              </button>
              <button type="button" className="underline text-muted" onClick={() => onDescartarSumido(d.id)}>
                Descartar ajuste
              </button>
            </div>
          </div>
        ))}
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
                      aria-label={`Texto da cláusula ${item.numero}`}
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
                  <div className="flex flex-wrap gap-3 items-start">
                    <p className={`flex-1 text-sm ${item.ajustado ? "bg-warning/[0.12] border-l-2 border-warning pl-2" : ""}`}>
                      <span className="font-medium">{item.numero}.</span> {item.texto}
                      {item.ajustado && <span className="ml-2 text-[11px] font-medium text-warning">Ajustado à mão</span>}
                      {item.status === "padrao_mudou" && <span className="ml-2 text-[11px] font-medium text-warning">Ajuste pendente</span>}
                      {item.status === "padrao_mudou" && (
                        <span className="block text-xs text-warning mt-1">
                          O texto padrão deste item mudou: revise ou reaplique seu ajuste. Enquanto isso, o contrato sai com o texto padrão.
                        </span>
                      )}
                    </p>
                    {reaplicando === item.id && (
                      <div className="order-last basis-full text-sm border border-warning rounded-lg p-3 space-y-2 bg-warning/[0.06]">
                        <p className="font-medium">Confirmar: o texto padrão mudou desde o seu ajuste.</p>
                        <p><span className="text-muted">Padrão de antes:</span> {item.padrao_ajuste || "(não registrado)"}</p>
                        <p><span className="text-muted">Padrão agora:</span> {item.padrao}</p>
                        <p><span className="text-muted">Seu ajuste:</span> {item.ajuste}</p>
                        <div className="flex gap-2 flex-wrap">
                          <button
                            type="button"
                            disabled={salvando}
                            className="px-3 py-1.5 rounded-lg bg-primary text-white text-sm disabled:opacity-50"
                            onClick={() => {
                              onReaplicar(item);
                              setReaplicando(null);
                            }}
                          >
                            Reaplicar meu ajuste a esta cláusula
                          </button>
                          <button type="button" onClick={() => setReaplicando(null)} className="px-3 py-1.5 rounded-lg border border-border text-sm">
                            Cancelar
                          </button>
                        </div>
                      </div>
                    )}
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
                          {item.status === "padrao_mudou" && (
                            <button type="button" disabled={salvando} className="text-primary-dark underline" onClick={() => setReaplicando(item.id)}>
                              Reaplicar meu ajuste
                            </button>
                          )}
                          {item.ajuste !== null && (
                            <button type="button" disabled={salvando} className="text-muted underline" onClick={() => onVoltar(item)}>
                              {item.ajustado ? "Voltar ao texto padrão" : "Descartar ajuste"}
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
