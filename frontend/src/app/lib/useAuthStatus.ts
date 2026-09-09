"use client";

import { useSession } from "next-auth/react";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

/**
 * O login de dev usa o cookie dev_session (ver layout.tsx), não uma sessão next-auth
 * real — sessionStatus do useSession() nunca vira "authenticated" nesse modo, então
 * telas que só buscam dados quando sessionStatus === "authenticated" ficam
 * "Carregando..." para sempre. Mesmo tratamento já usado em AcessoConsumidor.tsx.
 */
export function useAuthStatus(): AuthStatus {
  const { status } = useSession();
  const devMode = process.env.NEXT_PUBLIC_DEV_MODE === "true";
  return devMode ? "authenticated" : status;
}
