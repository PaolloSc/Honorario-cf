"use client";
 
import type { ContratoFormData, EscopoItem } from "@/types/contract";
import { ESCOPO_LABELS } from "@/types/contract";
 
const HONORARIO_LABELS: Record<string, string> = {
  hora_trabalhada: "Hora Trabalhada",
  pro_labore: "Pró-labore",
  mensalidade: "Mensalidade",
  exito: "Êxito",
  permuta: "Permuta",
};
 
function formatCurrency(val: number): string {
  return val.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}
 
interface Step6Props {
  data: ContratoFormData;
}
 
export default function Step6Revisao({ data }: Step6Props) {
  return (
    <div>
      <h2 className="text-xl font-bold text-primary mb-2">
        6. Revisão do Contrato
      </h2>
      <p className="text-sm text-muted mb-6">
        Revise todas as informações antes de gerar o contrato.
      </p>
 
      {/* Contratantes */}
      <Section title="Contratante(s)">
        {data.contratantes.map((c, i) => (
          <div key={i} className="mb-3">
            <p className="text-sm font-medium">Contratante {i + 1}:</p>
            {c.tipo === "PF" ? (
              <div className="text-sm text-muted ml-4">
                <p>{c.nome} - CPF: {c.cpf}</p>
                <p>{c.profissao}, {c.estado_civil}, {c.nacionalidade}</p>
                <p>{c.endereco}</p>
                <p>{c.email}</p>
              </div>
            ) : (
              <div className="text-sm text-muted ml-4">
                <p>{c.razao_social} - CNPJ: {c.cnpj}</p>
                <p>{c.endereco}</p>
                <p>{c.email}</p>
                {c.representante_nome && (
                  <p>Representante: {c.representante_nome}</p>
                )}
              </div>
            )}
          </div>
        ))}
        {data.incluir_partes_relacionadas && (
          <p className="text-xs text-accent font-medium mt-2">
            Cláusula de Partes Relacionadas inclusa
          </p>
        )}
      </Section>
 
      {/* Escopos */}
      <Section title="Escopos e Honorários">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 pr-4 font-semibold">Escopo</th>
                <th className="text-left py-2 font-semibold">Preço</th>
              </tr>
            </thead>
            <tbody>
              {data.escopos.map((escopo, i) => (
                <tr key={i} className="border-b border-border/50">
                  <td className="py-2 pr-4">
                    {ESCOPO_LABELS[escopo.tipo] ||
                      escopo.descricao_custom ||
                      "—"}
                    {escopo.numero_autos && (
                      <span className="text-xs text-muted block">
                        Autos: {escopo.numero_autos}
                      </span>
                    )}
                  </td>
                  <td className="py-2">
                    <PrecoResumo escopo={escopo} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
 
      {/* Acessórios */}
      <Section title="Acessórios">
        <ul className="text-sm text-muted space-y-1 ml-4 list-disc">
          <li>
            Reembolso:{" "}
            {data.acessorios.tem_reembolso
              ? data.acessorios.reembolso_limitado
                ? `Sim, com limitação: ${data.acessorios.descricao_limitacao_reembolso}`
                : "Sim, integral"
              : "Não"}
          </li>
          <li>
            Penalidade por inadimplemento:{" "}
            {data.acessorios.tem_penalidade_inadimplemento ? "Sim" : "Não"}
          </li>
          {data.acessorios.valor_diligencia && (
            <li>
              Valor da diligência:{" "}
              {formatCurrency(data.acessorios.valor_diligencia)} por ato
            </li>
          )}
        </ul>
      </Section>
 
      {/* Participação */}
      {data.participacao.tem_participacao && (
        <Section title="Participações (Interno)">
          <ul className="text-sm text-muted space-y-1 ml-4 list-disc">
            <li>
              Valor/Percentual: {data.participacao.percentual_ou_valor}
            </li>
            <li>Para: {data.participacao.para_quem}</li>
            <li>Natureza: {data.participacao.natureza}</li>
            <li>
              Captação: {data.participacao.responsavel_captacao}
            </li>
            <li>Gestão: {data.participacao.responsavel_gestao}</li>
          </ul>
        </Section>
      )}
    </div>
  );
}
 
function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-card border border-border rounded-xl p-4 mb-4 shadow-sm">
      <h3 className="font-semibold text-foreground mb-3 text-sm">{title}</h3>
      {children}
    </div>
  );
}
 
function PrecoResumo({ escopo }: { escopo: EscopoItem }) {
  const parts: string[] = [];
 
  for (const tipo of escopo.honorarios) {
    if (tipo === "hora_trabalhada" && escopo.hora_trabalhada) {
      parts.push(
        `${formatCurrency(escopo.hora_trabalhada.valor_hora)}/hora`
      );
    } else if (tipo === "pro_labore" && escopo.pro_labore) {
      parts.push(
        `${formatCurrency(escopo.pro_labore.valor_total)} pró-labore`
      );
    } else if (tipo === "mensalidade" && escopo.mensalidade) {
      parts.push(
        `${formatCurrency(escopo.mensalidade.valor)}/mês`
      );
    } else if (tipo === "exito" && escopo.exito?.percentual) {
      parts.push(`${escopo.exito.percentual}% êxito`);
    } else if (tipo === "permuta" && escopo.permuta) {
      parts.push(`Permuta: ${escopo.permuta.objeto_permuta}`);
    } else {
      parts.push(HONORARIO_LABELS[tipo] || tipo);
    }
  }
 
  return (
    <span className="text-sm">
      {parts.length > 0 ? parts.join(" + ") : "A definir"}
    </span>
  );
}