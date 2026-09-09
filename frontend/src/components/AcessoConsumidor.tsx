"use client";

import { podeUsarConsumidor } from "@/app/lib/api";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

// "carregando" | "sim" | "nao" (negado) | "erro" (não deu para perguntar).
// Separar negado de erro evita acusar falta de permissão quando, na verdade,
// o backend não respondeu.
export type Acesso = null | "sim" | "nao" | "erro";

/** Consulta o backend se o usuário pode usar o contrato de Ação de Consumo. */
export function useAcessoConsumidorDetalhado(): { acesso: Acesso; detalhe: string } {
  const { status } = useSession();
  const devMode = process.env.NEXT_PUBLIC_DEV_MODE === "true";
  const [acesso, setAcesso] = useState<Acesso>(null);
  const [detalhe, setDetalhe] = useState("");

  useEffect(() => {
    if (status !== "authenticated" && !devMode) return;
    let ativo = true;
    podeUsarConsumidor()
      .then((r) => ativo && setAcesso(r.permitido ? "sim" : "nao"))
      .catch((e) => {
        if (!ativo) return;
        setAcesso("erro");
        setDetalhe(e instanceof Error ? e.message : "falha de rede");
      });
    return () => {
      ativo = false;
    };
  }, [status, devMode]);

  return { acesso, detalhe };
}

/** Versão booleana, para esconder menu e botões. */
export function useAcessoConsumidor(): boolean | null {
  const { acesso } = useAcessoConsumidorDetalhado();
  if (acesso === null) return null;
  return acesso === "sim";
}

export default function AcessoConsumidor({ children }: { children: React.ReactNode }) {
  const { acesso, detalhe } = useAcessoConsumidorDetalhado();

  if (acesso === null) return null;

  if (acesso === "erro") {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center">
        <h1 className="font-display text-xl font-semibold text-primary-dark">
          Não foi possível verificar seu acesso
        </h1>
        <p className="text-sm text-muted mt-2">
          O sistema não conseguiu falar com o servidor. Isso não significa que você não tem
          permissão — tente novamente em instantes.
        </p>
        {detalhe && <p className="text-xs text-muted mt-3 font-mono">{detalhe}</p>}
      </div>
    );
  }

  if (acesso === "nao") {
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
