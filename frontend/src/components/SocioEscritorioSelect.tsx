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
    <div className="w-full mb-2 p-4 rounded-lg bg-card border border-purple-300/40">
      <label htmlFor="socio-escritorio" className="block text-sm font-medium text-purple-900 mb-1">
        Assinatura pelo escritório (obrigatório)
      </label>
      <p className="text-xs text-purple-700 mb-3">
        O sócio que assina como <strong>CONTRATADO</strong> pelo Carvalho &amp; Furtado. Vem sugerido
        pela área do contrato. Se ele também estiver entre os advogados que assinam, recebe um
        convite só.
      </p>
      <select
        id="socio-escritorio"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full sm:w-80 px-3 py-1.5 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-purple-300"
      >
        <option value="">Selecione o sócio...</option>
        {socios.map((s) => (
          <option key={s.email} value={s.email}>
            {s.name}
            {s.areas.length > 0 ? ` (${s.areas.join(", ")})` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
