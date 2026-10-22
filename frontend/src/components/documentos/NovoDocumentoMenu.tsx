"use client";

import type { ReactNode } from "react";

const CARTAO = "flex gap-3.5 items-start p-4 rounded-xl border bg-card min-h-11 transition";
const ICONE = "shrink-0 w-10 h-10 rounded-lg flex items-center justify-center";
const TRACO = { fill: "none", stroke: "currentColor", strokeWidth: 1.9, strokeLinecap: "round", strokeLinejoin: "round" } as const;

function Bloco({ href, titulo, descricao, alerta, children }: {
  href: string; titulo: string; descricao: string; alerta?: boolean; children: ReactNode;
}) {
  return (
    <a href={href} className={`${CARTAO} ${alerta ? "border-danger/30 hover:border-danger" : "border-border hover:border-primary"}`}>
      <span className={`${ICONE} ${alerta ? "bg-danger/[0.08] text-danger" : "bg-primary/[0.08] text-primary"}`}>
        <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" {...TRACO}>{children}</svg>
      </span>
      <span>
        <span className={`block font-semibold text-[15px] ${alerta ? "text-danger" : "text-foreground"}`}>{titulo}</span>
        <span className="block mt-0.5 text-[13px] text-muted leading-snug">{descricao}</span>
      </span>
    </a>
  );
}

/** Seção da página do contrato com os três documentos que nascem dele: aditivo, substabelecimento e distrato. */
export default function NovoDocumentoMenu({
  contratoId,
  distratoId,
}: {
  contratoId: string;
  /** contract_id do distrato já criado (não cancelado), se houver. */
  distratoId?: string;
}) {
  const url = (tipo: string) => `/documentos/novo?tipo=${tipo}&origem=${contratoId}`;
  return (
    <section aria-labelledby="docs-do-contrato" className="mb-8 border-t border-border pt-6">
      <h2 id="docs-do-contrato" className="font-display text-base font-semibold text-foreground">Documentos deste contrato</h2>
      <p className="text-sm text-muted mt-1 mb-3.5">Partes e dados do contrato já vêm preenchidos.</p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
        <Bloco href={url("aditivo")} titulo="Fazer aditivo" descricao="Muda objeto, valor ou empresas atendidas">
          <path d="M12 5v14M5 12h14" />
        </Bloco>
        <Bloco href={url("substabelecimento")} titulo="Fazer substabelecimento" descricao="Passa processos para outros advogados">
          <path d="M7 7h11l-3-3M17 17H6l3 3" />
        </Bloco>
        {distratoId ? (
          <Bloco href={`/contracts/${distratoId}`} titulo="Distrato já criado" descricao="Abrir" alerta>
            <circle cx="12" cy="12" r="9" /><path d="M8 12h8" />
          </Bloco>
        ) : (
          <Bloco href={url("distrato")} titulo="Encerrar contrato (distrato)" descricao="Fim do contrato e o que ainda é devido" alerta>
            <circle cx="12" cy="12" r="9" /><path d="M8 12h8" />
          </Bloco>
        )}
      </div>
    </section>
  );
}
