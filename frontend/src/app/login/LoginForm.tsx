"use client";

import { signIn } from "next-auth/react";
import { useState } from "react";
import Logo from "@/components/ui/Logo";

export default function LoginForm({
  callbackUrl,
  limpo = false,
}: {
  callbackUrl: string;
  limpo?: boolean;
}) {
  const [pending, setPending] = useState(false);
  const [falhou, setFalhou] = useState(false);

  // signIn() era chamado sem tratar o retorno: quando a chamada morria no
  // navegador (cookie de CSRF corrompido e' o caso comum), o botao ficava
  // "Redirecionando…" para sempre, desabilitado e sem dizer nada. A pessoa
  // ficava sem saida numa tela que parecia estar carregando.
  const entrar = () => {
    setPending(true);
    setFalhou(false);

    // Caminho feliz: a pagina navega para a Microsoft e este timer morre junto.
    const semResposta = setTimeout(() => {
      setPending(false);
      setFalhou(true);
    }, 8000);

    Promise.resolve(signIn("microsoft-entra-id", { callbackUrl })).catch(() => {
      clearTimeout(semResposta);
      setPending(false);
      setFalhou(true);
    });
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-6">
            <Logo variant="dark" format="vertical" className="h-24 w-auto" />
          </div>
          <h1 className="font-display text-xl font-semibold text-primary-dark tracking-wide">
            C&amp;F Advogados
          </h1>
          <p className="text-sm text-muted mt-2">
            Faça login com sua conta Microsoft do escritório.
          </p>
        </div>

        <button
          type="button"
          disabled={pending}
          onClick={entrar}
          className="w-full flex items-center justify-center gap-3 px-6 py-3 bg-primary-dark text-white rounded-lg font-medium hover:bg-primary-dark/90 transition shadow-sm disabled:opacity-60"
        >
          <svg className="w-5 h-5" viewBox="0 0 21 21" fill="none">
            <rect x="1" y="1" width="9" height="9" fill="#F25022" />
            <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
            <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
            <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
          </svg>
          {pending ? "Redirecionando…" : "Entrar com Microsoft"}
        </button>

        {limpo && !falhou && (
          <p className="mt-4 rounded-lg border border-primary/30 bg-primary/10 px-4 py-3 text-sm text-primary-dark">
            Sessão anterior apagada. Pode entrar normalmente.
          </p>
        )}

        {falhou && (
          <div
            role="alert"
            className="mt-4 rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger"
          >
            <p className="font-medium">Não conseguimos abrir o login da Microsoft.</p>
            <p className="mt-1">
              {limpo
                ? "A sessão já foi apagada e mesmo assim não funcionou, então não é cookie. Avise o suporte."
                : "Costuma ser resquício de uma sessão antiga deste site."}
            </p>
            {!limpo && (
              // Link, nao fetch: sao cookies HttpOnly, quem apaga e' o servidor
              // na resposta da navegacao.
              <a
                href="/api/auth/limpar"
                className="mt-3 inline-block rounded-md bg-danger px-3 py-1.5 font-medium text-white transition hover:opacity-90"
              >
                Limpar sessão e tentar de novo
              </a>
            )}
          </div>
        )}

        <p className="text-xs text-muted text-center mt-6">
          Acesso restrito ao Carvalho &amp; Furtado Advogados.
        </p>
      </div>
    </div>
  );
}
