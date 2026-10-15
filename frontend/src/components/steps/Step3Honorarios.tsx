"use client";

import { useCallback, useRef, useState } from "react";
import FormField, {
  Checkbox,
  Input,
  Select,
  TextArea,
  Toggle,
} from "@/components/ui/FormField";
import { previewHonorarios } from "@/app/lib/api";
import CurrencyInput from "@/components/ui/CurrencyInput";
import DateRangePicker from "@/components/ui/DateRangePicker";
import DatePicker from "@/components/ui/DatePicker";
import type {
  ComDesconto,
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

// "2026-05-10" -> "em 10/05/2026": mostra no campo livre o vencimento que
// contratos antigos gravaram como data.
function vencimentoLegado(iso?: string): string {
  const [a, m, d] = (iso ?? "").split("-");
  return d ? `em ${d}/${m}/${a}` : "";
}

interface TextoLivreProps {
  onEditar: () => void;
  onSair: () => void;
  // Texto mexido e ainda não aprovado no pop-up; onAbrir abre a prévia pra aprovar.
  pendente: boolean;
  onAbrir: () => void;
}

function DescontoCampos({
  h,
  onChange,
  onEditar,
  onSair,
  pendente,
  onAbrir,
}: TextoLivreProps & { h: ComDesconto; onChange: (partial: ComDesconto) => void }) {
  const tipo = h.desconto_tipo ?? "percentual";
  return (
    <div className="md:col-span-2 pt-2 border-t border-border">
      <Toggle
        label="Desconto?"
        value={h.tem_desconto || false}
        onChange={(v) => onChange({ tem_desconto: v })}
      />
      {h.tem_desconto && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
          <FormField label="Condição do desconto">
            <Input
              value={h.desconto_condicao || ""}
              onChange={(e) => {
                onEditar();
                onChange({ desconto_condicao: e.target.value });
              }}
              onBlur={onSair}
              placeholder="Ex.: pagamento até a data de vencimento"
            />
          </FormField>
          <FormField label="Especificação do desconto">
            <Select
              value={tipo}
              onChange={(e) => onChange({ desconto_tipo: e.target.value as "percentual" | "livre" })}
              options={[
                { value: "percentual", label: "Percentual" },
                { value: "livre", label: "Livre" },
              ]}
            />
            {tipo === "percentual" ? (
              <Input
                className="mt-2"
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={h.desconto_percentual || ""}
                onChange={(e) => {
                  onEditar();
                  onChange({ desconto_percentual: parseFloat(e.target.value) || undefined });
                }}
                onBlur={onSair}
                placeholder="%"
              />
            ) : (
              <Input
                className="mt-2"
                value={h.desconto_livre || ""}
                onChange={(e) => {
                  onEditar();
                  onChange({ desconto_livre: e.target.value });
                }}
                onBlur={onSair}
                placeholder="Ex.: R$ 500,00 na primeira parcela"
              />
            )}
          </FormField>
        </div>
      )}
      {pendente && (
        <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-warning bg-warning/[0.1] px-3 py-2 text-xs text-warning">
          <span>Texto alterado e ainda não aprovado.</span>
          <button type="button" onClick={onAbrir} className="font-medium underline">
            Ver prévia e aprovar
          </button>
        </div>
      )}
    </div>
  );
}

interface Step3Props {
  escopos: EscopoItem[];
  onChange: (escopos: EscopoItem[]) => void;
}

export default function Step3Honorarios({ escopos, onChange }: Step3Props) {
  // Pop-up de prévia: aberto sob demanda ("Ver prévia e aprovar"). Editar um texto
  // livre o marca como pendente; aprovar no pop-up tira a pendência, e nova edição
  // volta a pedir aprovação — mas sem reabrir o pop-up sozinho.
  const [pendentes, setPendentes] = useState<Set<string>>(new Set());
  const marcar = (key: string, pendente: boolean) =>
    setPendentes((prev) => {
      if (prev.has(key) === pendente) return prev;
      const n = new Set(prev);
      if (pendente) n.add(key);
      else n.delete(key);
      return n;
    });
  // revisando: a IA ainda está corrigindo o português (o html já mostra o digitado).
  const [previa, setPrevia] = useState<{
    key?: string;
    html?: string;
    erro?: string;
    revisando?: boolean;
    findings?: Array<{ trecho: string; problema: string; sugestao: string }>;
    avisos?: Array<{ trecho: string; problema: string }>;
  } | null>(null);
  const pedido = useRef<AbortController | null>(null);

  const abrirPrevia = (key: string, escopo: EscopoItem, tipo: TipoHonorario) => {
    pedido.current?.abort();
    const ctrl = new AbortController();
    pedido.current = ctrl;
    setPrevia({ key });
    const body = { escopos: [{ ...escopo, honorarios: [tipo] }] };
    // 1ª chamada rápida (digitado em amarelo); 2ª com a IA, que troca o html ao chegar.
    previewHonorarios(body, ctrl.signal)
      .then(({ html }) => {
        setPrevia({ key, html, revisando: true });
        return previewHonorarios(body, ctrl.signal, true);
      })
      .then(({ html, findings, avisos, erro }) =>
        setPrevia({ key, html, findings, avisos, revisando: false, erro: erro ?? undefined })
      )
      .catch(() => {
        if (ctrl.signal.aborted) return;
        // Se a IA falhar, fica a prévia sem correções.
        setPrevia((p) => (p?.html ? { ...p, revisando: false } : { key, erro: "Não foi possível gerar a prévia." }));
      });
  };

  // Grava a sugestão da IA no campo de texto livre que contém o trecho e reabre a prévia.
  const aplicarCorrecao = (f: { trecho: string; sugestao: string }) => {
    if (!previa?.key) return;
    const [idxStr, tipo] = previa.key.split(":");
    const idx = Number(idxStr);
    const escopo = escopos[idx];
    const obj = (escopo as unknown as Record<string, Record<string, unknown> | undefined>)[tipo];
    const campo = obj && Object.keys(obj).find((k) => typeof obj[k] === "string" && (obj[k] as string).includes(f.trecho));
    if (!obj || !campo) return;
    const novo = {
      ...escopo,
      [tipo]: { ...obj, [campo]: (obj[campo] as string).replace(f.trecho, f.sugestao) },
    } as EscopoItem;
    onChange(escopos.map((e, i) => (i === idx ? novo : e)));
    abrirPrevia(previa.key, novo, tipo as TipoHonorario);
  };

  const textoLivre = (escopo: EscopoItem, tipo: TipoHonorario): TextoLivreProps => {
    const key = `${escopos.indexOf(escopo)}:${tipo}`;
    return {
      pendente: pendentes.has(key),
      onEditar: () => marcar(key, true),
      onSair: () => {},
      onAbrir: () => abrirPrevia(key, escopo, tipo),
    };
  };

  const fecharPrevia = () => {
    pedido.current?.abort();
    setPrevia(null);
  };
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
            tem_hora_urgencia: true,
            tem_hora_fora_expediente: true,
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
        <div className="bg-warning/[0.1] border border-warning rounded-lg p-4 text-warning text-sm">
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
                  <div className="bg-background border border-border rounded-lg p-4 mt-3">
                    <p className="text-sm font-medium text-foreground mb-3">
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
                        value={escopo.hora_trabalhada.tem_hora_urgencia ?? true}
                        onChange={(v) => updateHoraTrabalhada(idx, { tem_hora_urgencia: v })}
                      />
                      <Toggle
                        label="Fora do Expediente (+100%)?"
                        value={escopo.hora_trabalhada.tem_hora_fora_expediente ?? true}
                        onChange={(v) => updateHoraTrabalhada(idx, { tem_hora_fora_expediente: v })}
                      />

                      <div className="md:col-span-2 pt-2 border-t border-border">
                        <p className="text-xs font-medium text-foreground mb-2 uppercase tracking-wide">
                          Período do contrato
                        </p>
                        <DateRangePicker
                          dataInicio={escopo.hora_trabalhada.data_inicio}
                          dataFim={escopo.hora_trabalhada.data_fim}
                          onChange={(di, df, dur) => {
                            updateHoraTrabalhada(idx, {
                              data_inicio: di,
                              data_fim: df,
                              duracao_meses: dur,
                            });
                          }}
                        />
                      </div>

                      <DescontoCampos
                        h={escopo.hora_trabalhada}
                        onChange={(p) => updateHoraTrabalhada(idx, p)}
                        {...textoLivre(escopo, "hora_trabalhada")}
                      />
                    </div>
                  </div>
                )}

                {/* Pró-labore Details */}
                {escopo.honorarios.includes("pro_labore") && escopo.pro_labore && (
                  <div className="bg-background border border-border rounded-lg p-4 mt-3">
                    <p className="text-sm font-medium text-foreground mb-3">
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

                      {(() => {
                        const pl = escopo.pro_labore;
                        // contratos antigos só têm tem_parcelamento (sim = mensal)
                        const tipo = pl.tipo_parcelamento ?? (pl.tem_parcelamento ? "mensal" : "");
                        const livre = textoLivre(escopo, "pro_labore");
                        return (
                          <>
                            <FormField label="Tipo de parcelamento">
                              <Select
                                value={tipo}
                                onChange={(e) => {
                                  const v = e.target.value as "" | "mensal" | "customizado";
                                  updateProLabore(idx, {
                                    tipo_parcelamento: v || undefined,
                                    tem_parcelamento: v === "mensal",
                                  });
                                }}
                                options={[
                                  { value: "", label: "Parcela única" },
                                  { value: "mensal", label: "Mensal" },
                                  { value: "customizado", label: "Customizado" },
                                ]}
                              />
                            </FormField>

                            {tipo === "" && (
                              <FormField label="Vencimento (data)">
                                <DatePicker
                                  value={pl.vencimento_data}
                                  onChange={(v) =>
                                    updateProLabore(idx, { vencimento_data: v })
                                  }
                                />
                              </FormField>
                            )}

                            {tipo === "mensal" && (
                              <>
                                <FormField label="Número de parcelas">
                                  <Input
                                    type="number"
                                    value={pl.numero_parcelas || ""}
                                    onChange={(e) =>
                                      updateProLabore(idx, { numero_parcelas: parseInt(e.target.value) || 0 })
                                    }
                                    placeholder="0"
                                  />
                                </FormField>
                                <FormField label="Valor da Parcela (R$)">
                                  <CurrencyInput
                                    value={pl.valor_parcela || undefined}
                                    onChange={(v) =>
                                      updateProLabore(idx, { valor_parcela: v ?? 0 })
                                    }
                                    placeholder="0,00"
                                  />
                                </FormField>
                                <FormField label="Vencimento 1ª parcela (data)">
                                  <DatePicker
                                    value={pl.vencimento_parcelas_data}
                                    onChange={(v) =>
                                      updateProLabore(idx, { vencimento_parcelas_data: v })
                                    }
                                  />
                                </FormField>
                              </>
                            )}

                            {tipo === "customizado" && (
                              <div className="md:col-span-2">
                                <FormField label="Parcelamento customizado">
                                  <TextArea
                                    value={pl.parcelamento_customizado || ""}
                                    onChange={(e) => {
                                      livre.onEditar();
                                      updateProLabore(idx, { parcelamento_customizado: e.target.value });
                                    }}
                                    onBlur={livre.onSair}
                                    placeholder="Ex.: 50% na assinatura e 50% em 30 dias"
                                    rows={2}
                                  />
                                </FormField>
                              </div>
                            )}
                          </>
                        );
                      })()}

                      <DescontoCampos
                        h={escopo.pro_labore}
                        onChange={(p) => updateProLabore(idx, p)}
                        {...textoLivre(escopo, "pro_labore")}
                      />
                    </div>
                  </div>
                )}

                {/* Mensalidade Details */}
                {escopo.honorarios.includes("mensalidade") && escopo.mensalidade && (
                  <div className="bg-background border border-border rounded-lg p-4 mt-3">
                    <p className="text-sm font-medium text-foreground mb-3">
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

                      <div className="md:col-span-2 pt-2 border-t border-border">
                        <p className="text-xs font-medium text-foreground mb-2 uppercase tracking-wide">
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

                      <DescontoCampos
                        h={escopo.mensalidade}
                        onChange={(p) => updateMensalidade(idx, p)}
                        {...textoLivre(escopo, "mensalidade")}
                      />
                    </div>
                  </div>
                )}

                {/* Êxito Details */}
                {escopo.honorarios.includes("exito") && escopo.exito && (
                  <div className="bg-background border border-border rounded-lg p-4 mt-3">
                    <p className="text-sm font-medium text-foreground mb-3">
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
                            value={escopo.exito.percentual || ""}
                            onChange={(e) =>
                              updateExito(idx, { percentual: parseFloat(e.target.value) || 0 })
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
                        {(() => {
                          const fp = escopo.exito.forma_pagamento || "";
                          const presets = ["a_vista", "parcelado", "conforme_cumprimento"];
                          const isCustom = fp !== "" && !presets.includes(fp);
                          return (
                            <>
                              <Select
                                value={isCustom ? "outro" : fp}
                                onChange={(e) =>
                                  updateExito(idx, {
                                    forma_pagamento:
                                      e.target.value === "outro" ? "a definir" : e.target.value,
                                  })
                                }
                                options={[
                                  { value: "a_vista", label: "À vista" },
                                  { value: "parcelado", label: "Parcelado" },
                                  { value: "conforme_cumprimento", label: "Conforme cumprimento" },
                                  { value: "outro", label: "Outro (descrever)" },
                                ]}
                                placeholder="Selecione..."
                              />
                              {isCustom && (
                                <Input
                                  className="mt-2"
                                  value={fp}
                                  onChange={(e) =>
                                    updateExito(idx, { forma_pagamento: e.target.value })
                                  }
                                  placeholder="Ex.: quando da formalização do acordo"
                                />
                              )}
                            </>
                          );
                        })()}
                      </FormField>

                      <FormField label="Vencimento">
                        <Input
                          value={escopo.exito.vencimento || vencimentoLegado(escopo.exito.vencimento_data)}
                          onChange={(e) => {
                            textoLivre(escopo, "exito").onEditar();
                            // o texto livre substitui a data/observação de contratos antigos
                            updateExito(idx, {
                              vencimento: e.target.value,
                              vencimento_data: undefined,
                              vencimento_obs: undefined,
                            });
                          }}
                          onBlur={textoLivre(escopo, "exito").onSair}
                          placeholder="Ex.: 10 dias após o recebimento do Benefício"
                        />
                      </FormField>

                      <FormField label="Forma de parcelamento">
                        <Input
                          value={escopo.exito.forma_parcelamento || ""}
                          onChange={(e) => {
                            textoLivre(escopo, "exito").onEditar();
                            updateExito(idx, { forma_parcelamento: e.target.value });
                          }}
                          onBlur={textoLivre(escopo, "exito").onSair}
                          placeholder="Ex.: em até 3 parcelas mensais"
                        />
                      </FormField>

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

                      <DescontoCampos
                        h={escopo.exito}
                        onChange={(p) => updateExito(idx, p)}
                        {...textoLivre(escopo, "exito")}
                      />
                    </div>
                  </div>
                )}

                {/* Permuta Details */}
                {escopo.honorarios.includes("permuta") && escopo.permuta && (
                  <div className="bg-background border border-border rounded-lg p-4 mt-3">
                    <p className="text-sm font-medium text-foreground mb-3">
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

                      <DescontoCampos
                        h={escopo.permuta}
                        onChange={(p) => updatePermuta(idx, p)}
                        {...textoLivre(escopo, "permuta")}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {previa && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
          onClick={fecharPrevia}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Prévia da cláusula"
            className="bg-card border border-border rounded-lg p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto text-sm"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-medium">Como vai ficar no contrato</h3>
              <button type="button" onClick={fecharPrevia} className="text-muted" aria-label="Fechar">
                ✕
              </button>
            </div>
            {previa.erro ? (
              <p className="text-danger">{previa.erro}</p>
            ) : previa.html === undefined ? (
              <p className="text-muted">Gerando prévia...</p>
            ) : (
              <>
                <p className="text-xs text-muted mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span><mark style={{ background: "rgba(250,204,21,.35)" }}>amarelo</mark> = o que você escreveu</span>
                  <span><del style={{ background: "rgba(239,68,68,.18)", color: "#b91c1c" }}>riscado</del> = trecho corrigido</span>
                  <span><ins style={{ background: "rgba(34,197,94,.22)", textDecoration: "none" }}>verde</ins> = como a IA melhorou</span>
                </p>
                <div
                  className="space-y-2 text-justify [&_h3]:font-semibold [&_table]:w-full [&_td]:border [&_td]:border-border [&_td]:p-1"
                  dangerouslySetInnerHTML={{ __html: previa.html }}
                />
                {previa.revisando && <p className="text-muted mt-3">IA revisando o português...</p>}
                {previa.erro && <p className="text-warning mt-3">{previa.erro}</p>}
                {previa.findings && previa.findings.length > 0 && (
                  <ul className="mt-3 space-y-2 border-t border-border pt-3">
                    {previa.findings.map((f, i) => (
                      <li key={i}>
                        <span className="line-through text-danger">{f.trecho}</span> →{" "}
                        <span className="text-primary-dark font-medium">{f.sugestao}</span>
                        <span className="block text-xs text-muted">{f.problema}</span>
                        <button
                          type="button"
                          onClick={() => aplicarCorrecao(f)}
                          className="mt-1 px-2 py-0.5 border border-primary text-primary-dark rounded text-xs"
                        >
                          Aplicar correção
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {previa.avisos && previa.avisos.length > 0 && (
                  <ul className="mt-3 space-y-2 rounded-lg border border-warning bg-warning/[0.1] p-3 text-xs">
                    {previa.avisos.map((a, i) => (
                      <li key={i}>
                        <span className="font-medium text-warning">Condição ambígua:</span>{" "}
                        &ldquo;{a.trecho}&rdquo; — {a.problema}
                      </li>
                    ))}
                  </ul>
                )}
                {previa.findings && previa.findings.length === 0 && !previa.revisando && !previa.erro && (
                  <p className="text-muted mt-3">IA: nenhuma correção necessária.</p>
                )}
              </>
            )}
            <div className="flex justify-end mt-4">
              <button
                type="button"
                onClick={fecharPrevia}
                className="px-3 py-1.5 border border-border rounded text-xs mr-2"
              >
                Voltar e editar
              </button>
              <button
                type="button"
                disabled={!previa.html}
                onClick={() => {
                  if (previa.key) marcar(previa.key, false);
                  fecharPrevia();
                }}
                className="px-3 py-1.5 bg-primary-dark text-white rounded text-xs disabled:opacity-50"
              >
                Aprovar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

