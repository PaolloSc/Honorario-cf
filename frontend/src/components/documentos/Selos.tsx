"use client";

// Selo de tipo do contrato (lista, página do contrato e seção Documentos).
const TIPO_LABELS: Record<string, { label: string; color: string }> = {
  honorarios: { label: "Honorários", color: "bg-primary-light/40 text-primary-dark" },
  consumidor_aereo: { label: "Ação de Consumo", color: "bg-brand-marrom/15 text-brand-marrom" },
  aditivo: { label: "Aditivo", color: "bg-accent/15 text-accent" },
  distrato: { label: "Distrato", color: "bg-danger/[0.12] text-danger" },
  substabelecimento: { label: "Substabelecimento", color: "bg-warning/[0.16] text-warning" },
};

// Cada tipo abre num formulário diferente ao editar — sem o selo a pessoa clica "Editar"
// achando que é honorários e cai em outro formulário sem aviso.
export function TipoBadge({ tipo }: { tipo: string }) {
  const info = TIPO_LABELS[tipo] || { label: tipo, color: "bg-border/35 text-muted" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${info.color}`}>
      {info.label}
    </span>
  );
}
