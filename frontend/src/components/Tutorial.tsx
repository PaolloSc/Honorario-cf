"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { lerEtapa, ouvirEtapa, tourDaRota } from "@/app/lib/tutorial";

// Tour guiado: abre sozinho na primeira visita de cada tela e pelo botão "?".
// Visto/desligado fica no navegador da pessoa; sem localStorage, só não abre sozinho.
const DESLIGADO = "tutorial-desligado";
// Cores fixas da marca: o balão é sempre branco, mesmo no tema escuro, para saltar do fundo escurecido.
const VERDE = "#1a3b34";
const BEGE = "#d6d1c9";
// Escurecido do fundo: forte o bastante para o balão e o alvo saltarem, no claro e no escuro.
const ESCURO = "rgba(0,0,0,0.72)";
const visto = (chave: string) => `tutorial-visto:${chave}`;
function ler(k: string): string | null {
  try {
    return localStorage.getItem(k);
  } catch {
    return null;
  }
}
function gravar(k: string) {
  try {
    localStorage.setItem(k, "1");
  } catch {
    /* navegador sem storage: o tour volta a abrir, sem prejuízo */
  }
}

export default function Tutorial() {
  const pathname = usePathname();
  // No assistente, cada etapa tem o seu tour: trocar de etapa troca o tour.
  const etapa = useSyncExternalStore(ouvirEtapa, lerEtapa, () => 0);
  const tour = tourDaRota(pathname, etapa);
  const [passo, setPasso] = useState<number | null>(null);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const cartao = useRef<HTMLDivElement>(null);

  const fechar = useCallback(() => {
    if (tour) gravar(visto(tour.chave));
    setPasso(null);
  }, [tour]);

  // Primeira visita: abre sozinho depois que a tela monta.
  useEffect(() => {
    setPasso(null);
    if (!tour || ler(DESLIGADO) || ler(visto(tour.chave))) return;
    const t = setTimeout(() => setPasso(0), 800);
    return () => clearTimeout(t);
  }, [tour]);

  // Destaque do alvo: acompanha rolagem e redimensionamento.
  useEffect(() => {
    if (passo === null || !tour) return;
    const el = tour.passos[passo].alvo?.() ?? null;
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
    // Alvo escondido (menu fechado, tela estreita) mede 0x0: vira balão centralizado.
    const medir = () => {
      const r = el?.getBoundingClientRect();
      const novo = r && r.width > 0 && r.height > 0 ? r : null;
      setRect((ant) =>
        ant && novo && ant.top === novo.top && ant.left === novo.left && ant.width === novo.width && ant.height === novo.height
          ? ant
          : novo,
      );
    };
    medir();
    // Conteúdo que carrega depois (lista, avisos) empurra o alvo sem rolar a tela: remede sempre.
    const t = setInterval(medir, 250);
    window.addEventListener("resize", medir);
    window.addEventListener("scroll", medir, true);
    cartao.current?.focus();
    return () => {
      clearInterval(t);
      window.removeEventListener("resize", medir);
      window.removeEventListener("scroll", medir, true);
    };
  }, [passo, tour]);

  // Teclado: Esc fecha, setas navegam.
  useEffect(() => {
    if (passo === null || !tour) return;
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") fechar();
      else if (e.key === "ArrowRight") setPasso((p) => (p !== null && p < tour.passos.length - 1 ? p + 1 : p));
      else if (e.key === "ArrowLeft") setPasso((p) => (p ? p - 1 : p));
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [passo, tour, fechar]);

  if (!tour) return null;

  const atual = passo === null ? null : tour.passos[passo];
  const ultimo = passo === tour.passos.length - 1;
  // Alvo na metade de baixo da tela: o balão vai para cima, para não cobri-lo.
  const emCima = rect ? rect.top + rect.height / 2 > window.innerHeight / 2 : false;

  return (
    <>
      <button
        type="button"
        onClick={() => setPasso(0)}
        aria-label="Ajuda desta tela"
        title="Ajuda desta tela"
        className="fixed bottom-4 right-4 z-40 h-11 w-11 rounded-full bg-primary text-white text-lg font-semibold shadow-lg hover:bg-primary-dark transition"
      >
        ?
      </button>

      {atual && (
        <div className="fixed inset-0 z-[60]">
          {rect ? (
            <>
              {/* Escurecido em 4 faixas em volta do alvo (sombra de 9999px não escurece em todo navegador). */}
              {[
                { top: 0, left: 0, right: 0, height: Math.max(0, rect.top - 6) },
                { top: rect.bottom + 6, left: 0, right: 0, bottom: 0 },
                { top: rect.top - 6, left: 0, width: Math.max(0, rect.left - 6), height: rect.height + 12 },
                { top: rect.top - 6, left: rect.right + 6, right: 0, height: rect.height + 12 },
              ].map((s, i) => (
                <div key={i} className="fixed" style={{ ...s, backgroundColor: ESCURO }} onClick={fechar} />
              ))}
              {/* Recorte: anel bege + verde, visível no claro e no escuro. */}
              <div
                className="fixed rounded-lg pointer-events-none"
                style={{
                  top: rect.top - 6,
                  left: rect.left - 6,
                  width: rect.width + 12,
                  height: rect.height + 12,
                  boxShadow: `0 0 0 3px ${BEGE}, 0 0 0 6px ${VERDE}, 0 0 24px 8px rgba(214,209,201,0.5)`,
                }}
              />
            </>
          ) : (
            <div className="fixed inset-0" style={{ backgroundColor: ESCURO }} onClick={fechar} />
          )}
          <div
            ref={cartao}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby="tour-titulo"
            style={{ backgroundColor: "#fff", color: "#1f2723", borderTopColor: VERDE }}
            className={`fixed z-[61] left-1/2 -translate-x-1/2 w-[min(26rem,calc(100vw-2rem))] rounded-xl border-t-[6px] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.6)] outline-none ${
              rect ? (emCima ? "top-4" : "bottom-4") : "top-1/2 -translate-y-1/2"
            }`}
          >
            <p className="text-xs mb-1" style={{ color: "#5b5346" }}>
              {tour.nome} · {passo! + 1} de {tour.passos.length}
            </p>
            <h2 id="tour-titulo" className="font-display text-base font-semibold mb-1.5" style={{ color: VERDE }}>
              {atual.titulo}
            </h2>
            <p className="text-sm">{atual.texto}</p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => (ultimo ? fechar() : setPasso(passo! + 1))}
                style={{ backgroundColor: VERDE }}
                className="px-5 py-2.5 text-white rounded-lg text-sm font-semibold shadow hover:opacity-90"
              >
                {ultimo ? "Entendi" : "Próximo →"}
              </button>
              {passo! > 0 && (
                <button
                  type="button"
                  onClick={() => setPasso(passo! - 1)}
                  style={{ borderColor: VERDE, color: VERDE }}
                  className="px-4 py-2.5 border-2 rounded-lg text-sm font-medium hover:bg-black/5"
                >
                  Voltar
                </button>
              )}
              {!ultimo && (
                <button
                  type="button"
                  onClick={fechar}
                  style={{ borderColor: BEGE, color: "#3d4541" }}
                  className="ml-auto px-4 py-2.5 border-2 rounded-lg text-sm font-medium hover:bg-black/5"
                >
                  Pular tutorial
                </button>
              )}
            </div>
            <div className="mt-3 flex flex-wrap justify-between gap-2 text-xs">
              <Link href="/ajuda" onClick={fechar} className="underline" style={{ color: VERDE }}>
                Ver tudo em “Como usar”
              </Link>
              <button
                type="button"
                onClick={() => {
                  gravar(DESLIGADO);
                  fechar();
                }}
                className="hover:underline"
                style={{ color: "#5b5346" }}
              >
                Não abrir sozinho de novo
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
