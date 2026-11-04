"use client";

import { useEffect, useState } from "react";
import FormField, { Input, TextArea, Toggle } from "@/components/ui/FormField";
import CurrencyInput from "@/components/ui/CurrencyInput";
import DateRangePicker from "@/components/ui/DateRangePicker";
import type { Acessorios } from "@/types/contract";
import { clausulasDoTexto, clausulasParaTexto } from "@/app/lib/clausulasAdicionais";
 
interface Step4Props {
  acessorios: Acessorios;
  onChange: (acessorios: Acessorios) => void;
}
 
export default function Step4Acessorios({ acessorios, onChange }: Step4Props) {
  // Lista editável; o contrato guarda um texto com uma cláusula por linha. Os campos vazios
  // (recém-adicionados) só existem aqui: ao salvar são descartados.
  const [clausulas, setClausulas] = useState(() => clausulasDoTexto(acessorios.clausulas_adicionais));
  useEffect(() => {
    // Rascunho/contrato carregado de fora: refaz a lista. Edição local não dispara (o texto bate).
    if (clausulasParaTexto(clausulas) !== (acessorios.clausulas_adicionais ?? "")) {
      setClausulas(clausulasDoTexto(acessorios.clausulas_adicionais));
    }
  }, [acessorios.clausulas_adicionais]); // eslint-disable-line react-hooks/exhaustive-deps

  const atualizarClausulas = (novas: string[]) => {
    setClausulas(novas);
    onChange({ ...acessorios, clausulas_adicionais: clausulasParaTexto(novas) });
  };

  return (
    <div>
      <h2 className="text-xl font-bold text-primary mb-2">
        4. Acessórios
      </h2>
      <p className="text-sm text-muted mb-6">
        Configure vigência, reembolsos, despesas e penalidades.
      </p>
 
      <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
        <FormField
          label="Vigência"
          hint="Prazo específico do contrato. Deixe vazio para tempo indeterminado."
        >
          <DateRangePicker
            dataInicio={acessorios.vigencia_inicio}
            dataFim={acessorios.vigencia_fim}
            onChange={(di, df, dur) =>
              onChange({ ...acessorios, vigencia_inicio: di, vigencia_fim: df, vigencia_meses: dur })
            }
          />
        </FormField>

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
          hint="Serão incluídas numeradas, na ordem, em seção própria antes do Foro. Campos vazios são ignorados."
        >
          <div className="space-y-2">
            {clausulas.map((c, i) => (
              <div key={i} className="flex items-start gap-2">
                <TextArea
                  value={c}
                  onChange={(e) =>
                    atualizarClausulas(clausulas.map((x, idx) => (idx === i ? e.target.value : x)))
                  }
                  placeholder={`Cláusula adicional ${i + 1}...`}
                  rows={2}
                  aria-label={`Cláusula adicional ${i + 1}`}
                />
                {clausulas.length > 1 && (
                  <button
                    type="button"
                    onClick={() => atualizarClausulas(clausulas.filter((_, idx) => idx !== i))}
                    className="text-danger text-sm hover:underline shrink-0 pt-2"
                    aria-label={`Remover cláusula adicional ${i + 1}`}
                  >
                    Remover
                  </button>
                )}
              </div>
            ))}
            <button
              type="button"
              onClick={() => atualizarClausulas([...clausulas, ""])}
              className="px-3 py-1.5 border border-dashed border-primary-light text-primary rounded-lg text-sm font-medium hover:bg-primary-light/20 transition"
            >
              + Adicionar cláusula
            </button>
          </div>
        </FormField>
      </div>
    </div>
  );
}