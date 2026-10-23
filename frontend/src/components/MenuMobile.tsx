"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import NavConsumidor from "@/components/NavConsumidor";

/** Menu do cabeçalho no celular (< sm): o nav de desktop fica oculto, então este botão abre os mesmos links. */
export default function MenuMobile() {
  const [aberto, setAberto] = useState(false);
  const pathname = usePathname();

  useEffect(() => setAberto(false), [pathname]);
  useEffect(() => {
    if (!aberto) return;
    const fechar = (e: KeyboardEvent) => e.key === "Escape" && setAberto(false);
    window.addEventListener("keydown", fechar);
    return () => window.removeEventListener("keydown", fechar);
  }, [aberto]);

  const link = "block px-4 py-3 text-sm font-medium text-white hover:bg-white/10 transition";
  return (
    <div className="sm:hidden relative">
      <button
        type="button"
        aria-label="Menu"
        aria-expanded={aberto}
        aria-controls="menu-mobile"
        onClick={() => setAberto((v) => !v)}
        className="flex h-10 w-10 items-center justify-center rounded-lg text-white hover:bg-white/10 transition"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          {aberto ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
        </svg>
      </button>
      {aberto && (
        <nav id="menu-mobile" className="absolute right-0 top-12 z-50 w-56 overflow-hidden rounded-lg bg-header-bg shadow-lg ring-1 ring-white/20">
          <Link href="/" className={link}>Honorários</Link>
          <NavConsumidor className={link} />
          <Link href="/contracts" className={link}>Contratos</Link>
        </nav>
      )}
    </div>
  );
}
