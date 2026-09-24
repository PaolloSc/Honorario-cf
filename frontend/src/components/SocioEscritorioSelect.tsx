"use client";

import type { ColaboradorWizard } from "@/app/lib/api";
import { ComboBox } from "@/components/ui/FormField";

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
      <div className="w-full sm:w-80" id="socio-escritorio">
        <ComboBox
          value={value}
          onChange={onChange}
          placeholder="Busque o sócio por nome ou letra"
          options={socios.map((s) => ({ value: s.email, label: s.name }))}
        />
      </div>
    </div>
  );
}
