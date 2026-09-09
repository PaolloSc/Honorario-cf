"use client";

import { useAcessoConsumidor } from "@/components/AcessoConsumidor";
import Link from "next/link";

/** Link do menu: só aparece para quem pode usar o contrato de Ação de Consumo. */
export default function NavConsumidor() {
  const permitido = useAcessoConsumidor();
  if (!permitido) return null;

  return (
    <Link
      href="/consumidor"
      className="text-brand-verde-claro/80 hover:text-white transition"
    >
      Ação de Consumo
    </Link>
  );
}
