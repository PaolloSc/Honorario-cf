"use client";

import FormField, { Input, TextArea, Toggle } from "@/components/ui/FormField";
import CurrencyInput from "@/components/ui/CurrencyInput";
import type { Acessorios } from "@/types/contract";
 
interface Step4Props {
  acessorios: Acessorios;
  onChange: (acessorios: Acessorios) => void;
}
 
export default function Step4Acessorios({ acessorios, onChange }: Step4Props) {
  return (
    <div>
      <h2 className="text-xl font-bold text-primary mb-2">
        4. Acessórios
      </h2>
      <p className="text-sm text-muted mb-6">
        Configure reembolsos, despesas e penalidades.
      </p>
 
      <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
        <Toggle
          label="Há reembolso de despesas?"
          value={acessorios.tem_reembolso}
          onChange={(v) => onChange({ ...acessorios, tem_reembolso: v })}
        />
 
        {acessorios.tem_reembolso && (
          <div className="ml-14 space-y-3">
            <Toggle
              label="O reembolso terá limitação?"
              value={acessorios.reembolso_limitado}
              onChange={(v) =>
                onChange({ ...acessorios, reembolso_limitado: v })
              }
            />
            {acessorios.reembolso_limitado && (
              <FormField label="Descreva a limitação do reembolso">
                <TextArea
                  value={acessorios.descricao_limitacao_reembolso || ""}
                  onChange={(e) =>
                    onChange({
                      ...acessorios,
                      descricao_limitacao_reembolso: e.target.value,
                    })
                  }
                  placeholder="Descreva as limitações de reembolso..."
                />
              </FormField>
            )}
          </div>
        )}
 
        <Toggle
          label="Haverá penalidade por inadimplemento?"
          value={acessorios.tem_penalidade_inadimplemento}
          onChange={(v) =>
            onChange({ ...acessorios, tem_penalidade_inadimplemento: v })
          }
        />
 
        <FormField
          label="Valor da Diligência Externa (R$)"
          hint="Diligências perante Cartório, Prefeitura, Receita Federal etc. Deixe vazio se não aplicável."
        >
          <CurrencyInput
            value={acessorios.valor_diligencia}
            onChange={(v) =>
              onChange({
                ...acessorios,
                valor_diligencia: v,
              })
            }
            placeholder="0,00"
          />
        </FormField>

        <FormField
          label="Custo de deslocamento por km (R$)"
          hint="Cobrado em serviço presencial fora da sede. Deixe vazio para usar o padrão de R$ 1,70/km."
        >
          <CurrencyInput
            value={acessorios.valor_km}
            onChange={(v) => onChange({ ...acessorios, valor_km: v })}
            placeholder="1,70"
          />
        </FormField>

        <FormField
          label="Critério de êxito em caso de extinção do contrato"
          hint='Substitui a tabela de fases processuais da cláusula de extinção — use quando não houver processo judicial (ex.: "assinatura do acordo"). Deixe vazio para manter a tabela padrão.'
        >
          <Input
            value={acessorios.criterio_extincao_exito || ""}
            onChange={(e) =>
              onChange({ ...acessorios, criterio_extincao_exito: e.target.value })
            }
            placeholder="Ex.: assinatura do acordo"
          />
        </FormField>

        <FormField
          label="Cláusulas adicionais"
          hint="Uma cláusula por linha. Serão incluídas numeradas em seção própria, antes do Foro."
        >
          <TextArea
            value={acessorios.clausulas_adicionais || ""}
            onChange={(e) =>
              onChange({ ...acessorios, clausulas_adicionais: e.target.value })
            }
            placeholder="Digite cada cláusula adicional em uma linha..."
            rows={4}
          />
        </FormField>
      </div>
    </div>
  );
}