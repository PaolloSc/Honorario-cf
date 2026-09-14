"use client";

import { signIn, useSession } from "next-auth/react";
import { setAccessToken } from "@/app/lib/api";

export default function AuthSync({ children }: { children: React.ReactNode }) {
  const { data: session } = useSession();

  // Set token synchronously during render (not useEffect) so child
  // components' effects already have the token available.
  setAccessToken(session?.accessToken || null);

  // O refresh do token junto ao Azure falhou (refresh token revogado, senha
  // trocada, 90 dias sem uso). A sessao next-auth ainda vale, entao o usuario
  // continua "logado" enquanto toda chamada a API volta 401 "Token expirado".
  // Avisamos sem redirecionar sozinhos: o wizard nao persiste os dados
  // digitados, e um signIn automatico jogaria fora o contrato em andamento.
  const sessaoQuebrada = session?.error === "RefreshAccessTokenError";

  return (
    <>
      {sessaoQuebrada && (
        <div
          role="alert"
          className="bg-danger/10 border-b border-danger/40 px-6 py-3 text-sm text-danger flex flex-wrap items-center justify-between gap-3"
        >
          <span>
            Sua sessão expirou. Entre novamente para continuar salvando e
            enviando contratos.
          </span>
          <button
            type="button"
            onClick={() => signIn("microsoft-entra-id")}
            className="rounded-md bg-danger px-3 py-1.5 font-medium text-white transition hover:opacity-90"
          >
            Entrar novamente
          </button>
        </div>
      )}
      {children}
    </>
  );
}
