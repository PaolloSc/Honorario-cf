"use client";

import { useAcessoConsumidor } from "@/components/AcessoConsumidor";
import Link from "next/link";

/** Link do menu: só aparece para quem pode usar o contrato de Ação de Consumo. */
export default function NavConsumidor({ className = "text-brand-verde-claro/80 hover:text-white transition" }: { className?: string }) {
  const permitido = useAcessoConsumidor();
  if (!permitido) return null;

  return (
    <Link
      href="/consumidor"
      className={className}
    >
      Ação de Consumo
    </Link>
  );
}
