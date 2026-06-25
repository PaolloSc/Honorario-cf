"use client";

import { useCallback } from "react";
import FormField, {
  Checkbox,
  Input,
  Select,
  Toggle,
} from "@/components/ui/FormField";
import CurrencyInput from "@/components/ui/CurrencyInput";
import DateRangePicker from "@/components/ui/DateRangePicker";
import DatePicker from "@/components/ui/DatePicker";
import type {
  EscopoItem,
  HoraTrabalhada,
  Mensalidade,
  ProLabore,
  Exito,
  Permuta,
  TipoHonorario,
  SubtipoMensalidade,
  VariacaoPrecoMensalidade,
  SubtipoExito,
} from "@/types/contract";
import { ESCOPO_LABELS } from "@/types/contract";

const HONORARIO_TYPES: Array<{ value: TipoHonorario; label: string }> = [
  { value: "hora_trabalhada", label: "Hora Trabalhada" },
  { value: "pro_labore", label: "Pró-labore" },
  { value: "mensalidade", label: "Mensalidade" },
  { value: "exito", label: "Êxito" },
  { value: "permuta", label: "Permuta" },
];

const SUBTIPO_MENSALIDADE = [
  { value: "advocacia_partido", label: "Advocacia de Partido" },
  { value: "por_processo", label: "Por Processo" },
  { value: "por_pasta", label: "Por Pasta" },
];

const VARIACAO_PRECO = [
  { value: "sem_variacao", label: "Sem Variação" },
  { value: "limitacao_temporal", label: "Com Limitação Temporal" },
  { value: "reducao_volume", label: "Com Redução por Volume" },
  { value: "variacao_fase_processual", label: "Com Variação por Fase Processual" },
];

const SUBTIPO_EXITO = [
  { value: "percentual_fixo", label: "Percentual Fixo" },
  { value: "percentual_variavel", label: "Percentual Variável" },
];

function calcHorasContratadas(
  ht: HoraTrabalhada,
  duracaoMeses?: number
): number | undefined {
  if (!ht.valor_hora || ht.valor_hora <= 0) return undefined;
  if (ht.tem_pacote_horas && ht.valor_pacote && ht.valor_pacote > 0) {
    return ht.valor_pacote / ht.valor_hora;
  }
  if (
    ht.tem_teto_mensal &&
    ht.valor_teto_mensal &&
    ht.valor_teto_mensal > 0 &&
    duracaoMeses &&
    duracaoMeses > 0
  ) {
    return (ht.valor_teto_mensal * duracaoMeses) / ht.valor_hora;
  }
  return undefined;
}

function formatHorasBR(v?: number): string {
  if (v == null || Number.isNaN(v)) return "";
  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(v);
}

interface Step3Props {
  escopos: EscopoItem[];
  onChange: (escopos: EscopoItem[]) => void;
}

export default function Step3Honorarios({ escopos, onChange }: Step3Props) {
  const updateEscopo = useCallback(
    (index: number, partial: Partial<EscopoItem>) => {
      const updated = [...escopos];
      updated[index] = { ...updated[index], ...partial };
      onChange(updated);
    },
    [escopos, onChange]
  );

  const toggleHonorario = useCallback(
    (escopoIdx: number, tipo: TipoHonorario, checked: boolean) => {
      const escopo = escopos[escopoIdx];
      let updated: EscopoItem;

      if (checked) {
        const newHonorarios = [...escopo.honorarios, tipo];
        updated = { ...escopo, honorarios: newHonorarios };

        // Initialize default data for the type
        if (tipo === "hora_trabalhada" && !escopo.hora_trabalhada) {
          updated.hora_trabalhada = {
            valor_hora: 0,
            tem_teto_mensal: false,
            tem_pacote_horas: false,
            tem_hora_urgencia: false,
            tem_hora_fora_expediente: false,
          };
        } else if (tipo === "pro_labore" && !escopo.pro_labore) {
          updated.pro_labore = {
            valor_total: 0,
            tem_parcelamento: false,
          };
        } else if (tipo === "mensalidade" && !escopo.mensalidade) {
          updated.mensalidade = {
            valor: 0,
            subtipo: "advocacia_partido",
            dia_vencimento: "5",
            variacao_preco: "sem_variacao",
          };
        } else if (tipo === "exito" && !escopo.exito) {
          updated.exito = {
            subtipo: "percentual_fixo",
            incidencia: "",
            base_calculo: "benefício econômico",
            vencimento: "",
            forma_pagamento: "",
            tem_beneficio_prospectivo: false,
            deduz_outro_honorario: false,
          };
        } else if (tipo === "permuta" && !escopo.permuta) {
          updated.permuta = {
            objeto_permuta: "",
            descricao: "",
            tem_torna: false,
          };
        }
      } else {
        const newHonorarios = escopo.honorarios.filter((h) => h !== tipo);
        updated = { ...escopo, honorarios: newHonorarios };
        // Remove associated data
        if (tipo === "hora_trabalhada") updated.hora_trabalhada = undefined;
        if (tipo === "pro_labore") updated.pro_labore = undefined;
        if (tipo === "mensalidade") updated.mensalidade = undefined;
        if (tipo === "exito") updated.exito = undefined;
        if (tipo === "permuta") updated.permuta = undefined;
      }

      const finalUpdated = [...escopos];
      finalUpdated[escopoIdx] = updated;
      onChange(finalUpdated);
    },
    [escopos, onChange]
  );

  const updateHoraTrabalhada = useCallback(
    (escopoIdx: number, partial: Partial<HoraTrabalhada>) => {
      const escopo = escopos[escopoIdx];
      const merged: HoraTrabalhada = { ...escopo.hora_trabalhada!, ...partial };
      const recalcFields = [
        "valor_hora",
        "valor_teto_mensal",
        "tem_teto_mensal",
        "valor_pacote",
        "tem_pacote_horas",
        "duracao_meses",
      ];
      const shouldRecalc =
        partial.horas_contratadas === undefined &&
        Object.keys(partial).some((k) => recalcFields.includes(k));
      if (shouldRecalc) {
        merged.horas_contratadas = calcHorasContratadas(merged, merged.duracao_meses);
      }
      const updated: EscopoItem = { ...escopo, hora_trabalhada: merged };
      const final = [...escopos];
      final[escopoIdx] = updated;
      onChange(final);
    },
    [escopos, onChange]
  );

  const updateProLabore = useCallback(
    (escopoIdx: number, partial: Partial<ProLabore>) => {
      const escopo = escopos[escopoIdx];
      const updated: EscopoItem = {
        ...escopo,
        pro_labore: { ...escopo.pro_labore!, ...partial },
      };
      const final = [...escopos];
      final[escopoIdx] = updated;
      onChange(final);
    },
    [escopos, onChange]
  );

  const updateMensalidade = useCallback(
    (escopoIdx: number, partial: Partial<Mensalidade>) => {
      const escopo = escopos[escopoIdx];
      const updated: EscopoItem = {
        ...escopo,
        mensalidade: { ...escopo.mensalidade!, ...partial },
      };
      const final = [...escopos];
      final[escopoIdx] = updated;
      onChange(final);
    },
    [escopos, onChange]
  );

  const updateExito = useCallback(
    (escopoIdx: number, partial: Partial<Exito>) => {
      const escopo = escopos[escopoIdx];
      const updated: EscopoItem = {
        ...escopo,
        exito: { ...escopo.exito!, ...partial },
      };
      const final = [...escopos];
      final[escopoIdx] = updated;
      onChange(final);
    },
    [escopos, onChange]
  );

  const updatePermuta = useCallback(
    (escopoIdx: number, partial: Partial<Permuta>) => {
      const escopo = escopos[escopoIdx];
      const updated: EscopoItem = {
        ...escopo,
        permuta: { ...escopo.permuta!, ...partial },
      };
      const final = [...escopos];
      final[escopoIdx] = updated;
      onChange(final);
    },
    [escopos, onChange]
  );

  return (
    <div>
      <h2 className="text-xl font-bold text-primary mb-2">
        3. Honorários
      </h2>
      <p className="text-sm text-muted mb-6">
        Configure os tipos de honorário para cada escopo. Honorários são cumulativos.
      </p>

      {escopos.length === 0 ? (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-amber-800 text-sm">
          Volte à etapa anterior e adicione pelo menos um escopo.
        </div>
      ) : (
        <div className="space-y-6">
          {escopos.map((escopo, idx) => (
            <div key={idx} className="bg-card border border-border rounded-xl p-5 shadow-sm">
              <h3 className="font-semibold text-foreground mb-4">
                Escopo {idx + 1}: {ESCOPO_LABELS[escopo.tipo] ?? escopo.tipo}
              </h3>

              <div className="space-y-4">
                <p className="text-xs font-medium text-muted uppercase tracking-wide">
                  Selecione os tipos de honorário aplicáveis:
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {HONORARIO_TYPES.map((ht) => (
                    <Checkbox
                      key={ht.value}
                      label={ht.label}
                      checked={escopo.honorarios.includes(ht.value as TipoHonorario)}
                      onChange={(checked) => toggleHonorario(idx, ht.value as TipoHonorario, checked)}
                    />
                  ))}
                </div>

                {/* Hora Trabalhada Details */}
                {escopo.honorarios.includes("hora_trabalhada") && escopo.hora_trabalhada && (
                  <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 mt-3">
                    <p className="text-sm font-medium text-blue-900 mb-3">
                      Hora Trabalhada - Detalhes
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <FormField label="Valor da Hora (R$)">
                        <CurrencyInput
                          value={escopo.hora_trabalhada.valor_hora || undefined}
                          onChange={(v) =>
                            updateHoraTrabalhada(idx, { valor_hora: v ?? 0 })
                          }
                          placeholder="0,00"
                        />
                      </FormField>

                      <div className="flex flex-col gap-2">
                        <Toggle
                          label="Teto mensal?"
                          value={escopo.hora_trabalhada.tem_teto_mensal || false}
                          onChange={(v) => updateHoraTrabalhada(idx, { tem_teto_mensal: v })}
                        />
                        {escopo.hora_trabalhada.tem_teto_mensal && (
                          <FormField label="Valor do Teto (R$)">
                            <CurrencyInput
                              value={escopo.hora_trabalhada.valor_teto_mensal || undefined}
                              onChange={(v) =>
                                updateHoraTrabalhada(idx, { valor_teto_mensal: v ?? 0 })
                              }
                              placeholder="0,00"
                            />
                          </FormField>
                        )}
                      </div>

                      <Toggle
                        label="Pacote de horas?"
                        value={escopo.hora_trabalhada.tem_pacote_horas || false}
                        onChange={(v) => updateHoraTrabalhada(idx, { tem_pacote_horas: v })}
                      />
                      {escopo.hora_trabalhada.tem_pacote_horas && (
                        <>
                          <FormField label="Horas no pacote">
                            <Input
                              type="number"
                              value={escopo.hora_trabalhada.quantidade_horas_pacote || ""}
                              onChange={(e) =>
                                updateHoraTrabalhada(idx, { quantidade_horas_pacote: parseInt(e.target.value) || 0 })
                              }
                              placeholder="0"
                            />
                          </FormField>
                          <FormField label="Valor do Pacote (R$)">
                            <CurrencyInput
                              value={escopo.hora_trabalhada.valor_pacote || undefined}
                              onChange={(v) =>
                                updateHoraTrabalhada(idx, { valor_pacote: v ?? 0 })
                              }
                              placeholder="0,00"
                            />
                          </FormField>
                        </>
                      )}

                      <Toggle
                        label="Urgência (+50%)?"
                        value={escopo.hora_trabalhada.tem_hora_urgencia ?? false}
                        onChange={(v) => updateHoraTrabalhada(idx, { tem_hora_urgencia: v })}
                      />
                      <Toggle
                        label="Fora do Expediente (+100%)?"
                        value={escopo.hora_trabalhada.tem_hora_fora_expediente ?? false}
                        onChange={(v) => updateHoraTrabalhada(idx, { tem_hora_fora_expediente: v })}
                      />

                      <div className="md:col-span-2 pt-2 border-t border-blue-200">
                        <p className="text-xs font-medium text-blue-900 mb-2 uppercase tracking-wide">
                          Período do contrato
                        </p>
                        <DateRangePicker
                          dataInicio={escopo.hora_trabalhada.data_inicio}
                          dataFim={escopo.hora_trabalhada.data_fim}
                          onChange={(di, df, dur) => {
                            const horasContratadas = calcHorasContratadas(
                              escopo.hora_trabalhada!,
                              dur
                            );
                            updateHoraTrabalhada(idx, {
                              data_inicio: di,
                              data_fim: df,
                              duracao_meses: dur,
                              horas_contratadas: horasContratadas,
                            });
                          }}
                        />
                      </div>

                      {(() => {
                        const horasContratadas = calcHorasContratadas(
                          escopo.hora_trabalhada,
                          escopo.hora_trabalhada.duracao_meses
                        );
                        const horasTrabalhadas = escopo.hora_trabalhada.horas_trabalhadas ?? 0;
                        const saldo = (horasContratadas ?? 0) - horasTrabalhadas;
                        return (
                          <div className="md:col-span-2 pt-2 border-t border-blue-200">
                            <p className="text-xs font-medium text-blue-900 mb-2 uppercase tracking-wide">
                              Horas
                            </p>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                              <div>
                                <label className="block text-sm font-semibold text-foreground mb-1">
                                  Horas contratadas
                                </label>
                                <input
                                  readOnly
                                  value={formatHorasBR(horasContratadas)}
                                  placeholder="—"
                                  className="w-full px-3 py-2 rounded-lg border border-border bg-gray-50 text-foreground text-sm cursor-not-allowed"
                                />
                              </div>
                              <FormField label="Horas já trabalhadas">
                                <Input
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  value={horasTrabalhadas || ""}
                                  onChange={(e) =>
                                    updateHoraTrabalhada(idx, {
                                      horas_trabalhadas: parseFloat(e.target.value) || 0,
                                    })
                                  }
                                  placeholder="0"
                                />
                              </FormField>
                              <div>
                                <label className="block text-sm font-semibold text-foreground mb-1">
                                  Saldo
                                </label>
                                <div
                                  className={`px-3 py-2 rounded-lg border text-sm ${
                                    horasContratadas == null
                                      ? "bg-gray-50 border-border text-muted"
                                      : saldo > 0
                                        ? "bg-green-50 border-green-200 text-green-800"
                                        : saldo < 0
                                          ? "bg-red-50 border-red-200 text-red-800"
                                          : "bg-amber-50 border-amber-200 text-amber-800"
                                  }`}
                                >
                                  {horasContratadas == null
                                    ? "—"
                                    : saldo > 0
                                      ? `Saldo positivo: ${formatHorasBR(saldo)} horas`
                                      : saldo < 0
                                        ? `Horas excedidas: ${formatHorasBR(Math.abs(saldo))} horas`
                                        : "Horas integralmente utilizadas"}
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  </div>
                )}

                {/* Pró-labore Details */}
                {escopo.honorarios.includes("pro_labore") && escopo.pro_labore && (
                  <div className="bg-green-50 border border-green-100 rounded-lg p-4 mt-3">
                    <p className="text-sm font-medium text-green-900 mb-3">
                      Pró-labore - Detalhes
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <FormField label="Valor Total (R$)">
                        <CurrencyInput
                          value={escopo.pro_labore.valor_total || undefined}
                          onChange={(v) =>
                            updateProLabore(idx, { valor_total: v ?? 0 })
                          }
                          placeholder="0,00"
                        />
                      </FormField>

                      {!escopo.pro_labore.tem_parcelamento && (
                        <FormField label="Vencimento (data)">
                          <DatePicker
                            value={escopo.pro_labore.vencimento_data}
                            onChange={(v) =>
                              updateProLabore(idx, { vencimento_data: v })
                            }
                          />
                        </FormField>
                      )}

                      <Toggle
                        label="Parcelamento?"
                        value={escopo.pro_labore.tem_parcelamento || false}
                        onChange={(v) => updateProLabore(idx, { tem_parcelamento: v })}
                      />
                      {escopo.pro_labore.tem_parcelamento && (
                        <>
                          <FormField label="Número de parcelas">
                            <Input
                              type="number"
                              value={escopo.pro_labore.numero_parcelas || ""}
                              onChange={(e) =>
                                updateProLabore(idx, { numero_parcelas: parseInt(e.target.value) || 0 })
                              }
                              placeholder="0"
                            />
                          </FormField>
                          <FormField label="Valor da Parcela (R$)">
                            <CurrencyInput
                              value={escopo.pro_labore.valor_parcela || undefined}
                              onChange={(v) =>
                                updateProLabore(idx, { valor_parcela: v ?? 0 })
                              }
                              placeholder="0,00"
                            />
                          </FormField>
                          <FormField label="Vencimento 1ª parcela (data)">
                            <DatePicker
                              value={escopo.pro_labore.vencimento_parcelas_data}
                              onChange={(v) =>
                                updateProLabore(idx, { vencimento_parcelas_data: v })
                              }
                            />
                          </FormField>
                        </>
                      )}

                      <div className="md:col-span-2 pt-2 border-t border-green-200">
                        <p className="text-xs font-medium text-green-900 mb-2 uppercase tracking-wide">
                          Vigência
                        </p>
                        <DateRangePicker
                          dataInicio={escopo.pro_labore.data_inicio}
                          dataFim={escopo.pro_labore.data_fim}
                          onChange={(di, df, dur) =>
                            updateProLabore(idx, {
                              data_inicio: di,
                              data_fim: df,
                              duracao_meses: dur,
                            })
                          }
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Mensalidade Details */}
                {escopo.honorarios.includes("mensalidade") && escopo.mensalidade && (
                  <div className="bg-purple-50 border border-purple-100 rounded-lg p-4 mt-3">
                    <p className="text-sm font-medium text-purple-900 mb-3">
                      Mensalidade - Detalhes
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <FormField label="Valor Mensal (R$)">
                        <CurrencyInput
                          value={escopo.mensalidade.valor || undefined}
                          onChange={(v) =>
                            updateMensalidade(idx, { valor: v ?? 0 })
                          }
                          placeholder="0,00"
                        />
                      </FormField>

                      <FormField label="1º vencimento (data)">
                        <DatePicker
                          value={escopo.mensalidade.dia_vencimento_data}
                          onChange={(v) =>
                            updateMensalidade(idx, { dia_vencimento_data: v })
                          }
                        />
                      </FormField>

                      <FormField label="Subtipo">
                        <Select
                          value={escopo.mensalidade.subtipo || "advocacia_partido"}
                          onChange={(e) =>
                            updateMensalidade(idx, { subtipo: e.target.value as SubtipoMensalidade })
                          }
                          options={SUBTIPO_MENSALIDADE}
                        />
                      </FormField>

                      <FormField label="Variação de preço">
                        <Select
                          value={escopo.mensalidade.variacao_preco || "sem_variacao"}
                          onChange={(e) =>
                            updateMensalidade(idx, { variacao_preco: e.target.value as VariacaoPrecoMensalidade })
                          }
                          options={VARIACAO_PRECO}
                        />
                      </FormField>

                      {escopo.mensalidade.variacao_preco === "limitacao_temporal" && (
                        <FormField label="Anos de limitação">
                          <Input
                            type="number"
                            value={escopo.mensalidade.limitacao_temporal_anos || ""}
                            onChange={(e) =>
                              updateMensalidade(idx, { limitacao_temporal_anos: parseInt(e.target.value) || 0 })
                            }
                            placeholder="Ex: 2"
                          />
                        </FormField>
                      )}

                      <div className="md:col-span-2 pt-2 border-t border-purple-200">
                        <p className="text-xs font-medium text-purple-900 mb-2 uppercase tracking-wide">
                          Período da mensalidade
                        </p>
                        <DateRangePicker
                          dataInicio={escopo.mensalidade.data_inicio}
                          dataFim={escopo.mensalidade.data_fim}
                          onChange={(di, df, dur) =>
                            updateMensalidade(idx, {
                              data_inicio: di,
                              data_fim: df,
                              duracao_meses: dur,
                            })
                          }
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Êxito Details */}
                {escopo.honorarios.includes("exito") && escopo.exito && (
                  <div className="bg-amber-50 border border-amber-100 rounded-lg p-4 mt-3">
                    <p className="text-sm font-medium text-amber-900 mb-3">
                      Êxito - Detalhes
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <FormField label="Subtipo">
                        <Select
                          value={escopo.exito.subtipo || "percentual_fixo"}
                          onChange={(e) =>
                            updateExito(idx, { subtipo: e.target.value as SubtipoExito })
                          }
                          options={SUBTIPO_EXITO}
                        />
                      </FormField>

                      {escopo.exito.subtipo === "percentual_fixo" && (
                        <FormField label="Percentual (%)">
                          <Input
                            type="number"
                            step="0.1"
                            min="0"
                            max="100"
                            value={escopo.exito.percentual || ""}
                            onChange={(e) =>
                              // ponytail: clampa 0-100 (type=number nao impede 150/-50)
                              updateExito(idx, { percentual: Math.min(100, Math.max(0, parseFloat(e.target.value) || 0)) })
                            }
                            placeholder="0"
                          />
                        </FormField>
                      )}

                      <FormField label="Incidência">
                        <Select
                          value={escopo.exito.incidencia || ""}
                          onChange={(e) =>
                            updateExito(idx, { incidencia: e.target.value })
                          }
                          options={[
                            { value: "beneficio_economico", label: "Benefício econômico" },
                            { value: "beneficio_financeiro", label: "Benefício financeiro" },
                            { value: "beneficio_tributario", label: "Benefício tributário" },
                            { value: "todos", label: "Todos os benefícios" },
                          ]}
                          placeholder="Selecione..."
                        />
                      </FormField>

                      <FormField label="Forma de pagamento">
                        <Select
                          value={escopo.exito.forma_pagamento || ""}
                          onChange={(e) =>
                            updateExito(idx, { forma_pagamento: e.target.value })
                          }
                          options={[
                            { value: "a_vista", label: "À vista" },
                            { value: "parcelado", label: "Parcelado" },
                            { value: "conforme_cumprimento", label: "Conforme cumprimento" },
                          ]}
                          placeholder="Selecione..."
                        />
                      </FormField>

                      <FormField label="Vencimento (data)">
                        <DatePicker
                          value={escopo.exito.vencimento_data}
                          onChange={(v) =>
                            updateExito(idx, { vencimento_data: v })
                          }
                        />
                      </FormField>

                      <div className="md:col-span-2 pt-2 border-t border-amber-200">
                        <p className="text-xs font-medium text-amber-900 mb-2 uppercase tracking-wide">
                          Período do êxito
                        </p>
                        <DateRangePicker
                          dataInicio={escopo.exito.data_inicio}
                          dataFim={escopo.exito.data_fim}
                          onChange={(di, df, dur) =>
                            updateExito(idx, {
                              data_inicio: di,
                              data_fim: df,
                              duracao_meses: dur,
                            })
                          }
                        />
                      </div>

                      <Toggle
                        label="Benefício prospectivo?"
                        value={escopo.exito.tem_beneficio_prospectivo || false}
                        onChange={(v) => updateExito(idx, { tem_beneficio_prospectivo: v })}
                      />
                      {escopo.exito.tem_beneficio_prospectivo && (
                        <div className="md:col-span-2">
                          <DateRangePicker
                            dataInicio={escopo.exito.prospectivo_data_inicio}
                            dataFim={escopo.exito.prospectivo_data_fim}
                            onChange={(di, df, dur) =>
                              updateExito(idx, {
                                prospectivo_data_inicio: di,
                                prospectivo_data_fim: df,
                                prospectivo_duracao_meses: dur,
                              })
                            }
                          />
                        </div>
                      )}

                      <Toggle
                        label="Deduz de outro honorário?"
                        value={escopo.exito.deduz_outro_honorario || false}
                        onChange={(v) => updateExito(idx, { deduz_outro_honorario: v })}
                      />
                      {escopo.exito.deduz_outro_honorario && (
                        <FormField label="Honorário a deduzir">
                          <Select
                            value={escopo.exito.honorario_deduzido || ""}
                            onChange={(e) =>
                              updateExito(idx, { honorario_deduzido: e.target.value })
                            }
                            options={[
                              { value: "pro_labore", label: "Pró-labore" },
                              { value: "mensalidade", label: "Mensalidade" },
                              { value: "hora_trabalhada", label: "Hora trabalhada" },
                            ]}
                            placeholder="Selecione..."
                          />
                        </FormField>
                      )}
                    </div>
                  </div>
                )}

                {/* Permuta Details */}
                {escopo.honorarios.includes("permuta") && escopo.permuta && (
                  <div className="bg-teal-50 border border-teal-100 rounded-lg p-4 mt-3">
                    <p className="text-sm font-medium text-teal-900 mb-3">
                      Permuta - Detalhes
                    </p>
                    <div className="grid grid-cols-1 gap-4">
                      <FormField label="Objeto da permuta">
                        <Input
                          value={escopo.permuta.objeto_permuta || ""}
                          onChange={(e) =>
                            updatePermuta(idx, { objeto_permuta: e.target.value })
                          }
                          placeholder="Ex: Serviços de contabilidade"
                        />
                      </FormField>

                      <FormField label="Descrição">
                        <Input
                          value={escopo.permuta.descricao || ""}
                          onChange={(e) =>
                            updatePermuta(idx, { descricao: e.target.value })
                          }
                          placeholder="Detalhes da permuta..."
                        />
                      </FormField>

                      <Toggle
                        label="Haverá torna (pagamento adicional)?"
                        value={escopo.permuta.tem_torna || false}
                        onChange={(v) => updatePermuta(idx, { tem_torna: v })}
                      />
                      {escopo.permuta.tem_torna && (
                        <>
                          <FormField label="Valor da Torna (R$)">
                            <CurrencyInput
                              value={escopo.permuta.valor_torna || undefined}
                              onChange={(v) =>
                                updatePermuta(idx, { valor_torna: v ?? 0 })
                              }
                              placeholder="0,00"
                            />
                          </FormField>
                          <FormField label="Forma de pagamento">
                            <Input
                              value={escopo.permuta.forma_pagamento_torna || ""}
                              onChange={(e) =>
                                updatePermuta(idx, { forma_pagamento_torna: e.target.value })
                              }
                              placeholder="Ex: À vista, 2 parcelas..."
                            />
                          </FormField>
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

