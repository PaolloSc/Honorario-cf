"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import FormularioDocumento from "@/components/documentos/FormularioDocumento";
import { ehDocumentoComplementar } from "@/app/lib/documentos";

// /documentos/novo?tipo=aditivo|distrato&origem=<contrato>; sem origem = contrato antigo fora do sistema
function Conteudo() {
  const params = useSearchParams();
  const tipo = params.get("tipo");
  const origem = params.get("origem");

  if (!ehDocumentoComplementar(tipo)) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12">
        <div className="rounded-lg border border-danger bg-danger/[0.08] p-4 text-sm text-danger">Tipo de documento inválido.</div>
        <a href="/contracts" className="mt-4 inline-block text-sm text-primary hover:underline">Voltar para a lista</a>
      </div>
    );
  }
  if (tipo === "substabelecimento") {  // não existe substabelecimento avulso: nasce pelo distrato
    return (
      <div className="max-w-3xl mx-auto px-4 py-12">
        <div className="rounded-lg border border-border bg-card p-4 text-sm text-foreground">
          O substabelecimento é gerado junto com o distrato: abra o contrato e use &ldquo;Encerrar contrato (distrato)&rdquo;.
        </div>
        <a href="/contracts" className="mt-4 inline-block text-sm text-primary hover:underline">Voltar para a lista</a>
      </div>
    );
  }
  return <FormularioDocumento key={`${tipo}-${origem}`} tipo={tipo} origemId={origem} />;
}

export default function NovoDocumentoPage() {
  return (
    <Suspense fallback={<div className="max-w-3xl mx-auto px-4 py-12 text-center text-muted">Carregando...</div>}>
      <Conteudo />
    </Suspense>
  );
}
