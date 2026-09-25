"use client";

import { signIn } from "next-auth/react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Logo from "@/components/ui/Logo";

export default function ConvitePage() {
  const { token } = useParams<{ token: string }>();
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    signIn("convite", { token, redirect: false }).then((r) => {
      if (r?.ok && !r.error) window.location.href = "/";
      else setFalhou(true);
    }, () => setFalhou(true));
  }, [token]);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-sm text-center">
        <div className="flex justify-center mb-6">
          <Logo variant="dark" format="vertical" className="h-24 w-auto" />
        </div>
        <p className="text-sm text-muted">
          {falhou ? "Link de acesso inválido ou expirado." : "Entrando…"}
        </p>
      </div>
    </div>
  );
}
