"use client";

import { podeUsarConsumidor } from "@/app/lib/api";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

/** Consulta o backend se o usuário pode usar o contrato de Ação de Consumo. */
export function useAcessoConsumidor() {
  const { status } = useSession();
  const devMode = process.env.NEXT_PUBLIC_DEV_MODE === "true";
  // null = ainda carregando; evita piscar o menu para quem não tem acesso.
  const [permitido, setPermitido] = useState<boolean | null>(null);

  useEffect(() => {
    if (status !== "authenticated" && !devMode) return;
    let ativo = true;
    podeUsarConsumidor()
      .then((r) => ativo && setPermitido(r.permitido))
      .catch(() => ativo && setPermitido(false));
    return () => {
      ativo = false;
    };
  }, [status, devMode]);

  return permitido;
}

export default function AcessoConsumidor({ children }: { children: React.ReactNode }) {
  const permitido = useAcessoConsumidor();

  if (permitido === null) return null;
  if (!permitido) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center">
        <h1 className="font-display text-xl font-semibold text-primary-dark">
          Acesso restrito
        </h1>
        <p className="text-sm text-muted mt-2">
          O contrato de Ação de Consumo está liberado apenas para a equipe indicada pelo
          escritório. Fale com o administrador do sistema se precisar de acesso.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
