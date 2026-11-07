"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { tourDaRota } from "@/app/lib/tutorial";

// Tour guiado: abre sozinho na primeira visita de cada tela e pelo botão "?".
// Visto/desligado fica no navegador da pessoa; sem localStorage, só não abre sozinho.
const DESLIGADO = "tutorial-desligado";
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
  const tour = tourDaRota(pathname);
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
    const medir = () => setRect(el ? el.getBoundingClientRect() : null);
    medir();
    const t = setTimeout(medir, 400); // depois da rolagem suave
    window.addEventListener("resize", medir);
    window.addEventListener("scroll", medir, true);
    cartao.current?.focus();
    return () => {
      clearTimeout(t);
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
        <div className="fixed inset-0 z-[60]" aria-hidden={false}>
          {rect ? (
            <div
              className="fixed rounded-lg ring-2 ring-primary pointer-events-none transition-all"
              style={{
                top: rect.top - 6,
                left: rect.left - 6,
                width: rect.width + 12,
                height: rect.height + 12,
                boxShadow: "0 0 0 9999px rgba(0,0,0,0.5)",
              }}
            />
          ) : (
            <div className="fixed inset-0 bg-black/50" onClick={fechar} />
          )}
          <div
            ref={cartao}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby="tour-titulo"
            className={`fixed left-1/2 -translate-x-1/2 w-[min(26rem,calc(100vw-2rem))] rounded-xl border border-border bg-card p-5 shadow-xl outline-none ${
              rect ? (emCima ? "top-4" : "bottom-4") : "top-1/2 -translate-y-1/2"
            }`}
          >
            <p className="text-xs text-muted mb-1">
              {tour.nome} · {passo! + 1} de {tour.passos.length}
            </p>
            <h2 id="tour-titulo" className="font-display text-base font-semibold text-primary-dark mb-1.5">
              {atual.titulo}
            </h2>
            <p className="text-sm text-foreground">{atual.texto}</p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => (ultimo ? fechar() : setPasso(passo! + 1))}
                className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark"
              >
                {ultimo ? "Entendi" : "Próximo"}
              </button>
              {passo! > 0 && (
                <button
                  type="button"
                  onClick={() => setPasso(passo! - 1)}
                  className="px-4 py-2 border border-border rounded-lg text-sm hover:bg-background"
                >
                  Voltar
                </button>
              )}
              {!ultimo && (
                <button type="button" onClick={fechar} className="px-2 py-2 text-sm text-muted hover:underline">
                  Pular
                </button>
              )}
            </div>
            <div className="mt-3 flex flex-wrap justify-between gap-2 text-xs">
              <Link href="/ajuda" onClick={fechar} className="text-primary hover:underline">
                Ver tudo em “Como usar”
              </Link>
              <button
                type="button"
                onClick={() => {
                  gravar(DESLIGADO);
                  fechar();
                }}
                className="text-muted hover:underline"
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
