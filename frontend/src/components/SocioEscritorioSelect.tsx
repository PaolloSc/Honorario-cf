"use client";

import type { ColaboradorWizard } from "@/app/lib/api";

// Assinatura pelo escritório: sempre um sócio (advogado não representa o C&F).
// Obrigatória — sem ela o backend recusa o envio.
export default function SocioEscritorioSelect({
  colaboradores,
  value,
  onChange,
}: {
  colaboradores: ColaboradorWizard[];
  value: string;
  onChange: (email: string) => void;
}) {
  const socios = colaboradores.filter((c) => c.role === "socio" && c.email);
  return (
    <div className="w-full mb-2 p-4 rounded-lg bg-card border border-border">
      <label htmlFor="socio-escritorio" className="block text-sm font-semibold text-foreground mb-1">
        Assinatura pelo escritório<span className="text-danger ml-1">*</span>
      </label>
      <p className="text-xs text-muted mb-3">
        Indique o sócio que assinará pelo escritório.
      </p>
      <select
        id="socio-escritorio"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full sm:w-80 px-3 py-1.5 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-primary/40"
      >
        <option value="">Selecione o sócio...</option>
        {socios.map((s) => (
          <option key={s.email} value={s.email}>
            {s.name}
          </option>
        ))}
      </select>
    </div>
  );
}
