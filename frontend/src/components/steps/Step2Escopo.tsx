"use client";

import FormField, {
  Checkbox,
  Input,
  TextArea,
  Toggle,
} from "@/components/ui/FormField";
import type {
  EscopoItem,
  TipoEscopo
} from "@/types/contract";
import { ESCOPO_LABELS } from "@/types/contract";
import { useCallback } from "react";

const ESCOPO_TYPES = Object.keys(ESCOPO_LABELS) as TipoEscopo[];

const GENERIC_DETAIL_LABELS: Partial<Record<TipoEscopo, string>> = {
  consultoria_contencioso_geral: "Detalhes da consultoria/contencioso",
  consultoria_lgpd: "Detalhes da consultoria LGPD",
  consultoria_compliance_trabalhista: "Detalhes do compliance trabalhista",
  consultoria_planejamento_tributario: "Detalhes do planejamento tributario",
  consultoria_diagnostico_fiscal: "Detalhes do diagnostico fiscal",
  consultoria_contratual: "Contratos ou temas a analisar",
};

function emptyEscopo(tipo: TipoEscopo): EscopoItem {
  return {
    tipo,
    honorarios: [],
    ...(tipo === "contencioso_memoriais"
      ? {
          subtipo_memoriais: {
            elaboracao_memoriais: false,
            despacho_memoriais: false,
            sustentacao_oral_relator: false,
            sustentacao_oral_todos_julgadores: false,
          },
        }
      : {}),
  };
}

interface Step2Props {
  escopos: EscopoItem[];
  onChange: (escopos: EscopoItem[]) => void;
  incluirPartesRelacionadas: boolean;
  onChangePartesRelacionadas: (val: boolean) => void;
}

export default function Step2Escopo({
  escopos,
  onChange,
  incluirPartesRelacionadas,
  onChangePartesRelacionadas,
}: Step2Props) {
  const toggleEscopo = useCallback(
    (tipo: TipoEscopo, enabled: boolean) => {
      if (enabled) {
        onChange([...escopos, emptyEscopo(tipo)]);
      } else {
        onChange(escopos.filter((e) => e.tipo !== tipo));
      }
    },
    [escopos, onChange]
  );

  const updateEscopo = useCallback(
    (index: number, partial: Partial<EscopoItem>) => {
      const updated = [...escopos];
      updated[index] = { ...updated[index], ...partial };
      onChange(updated);
    },
    [escopos, onChange]
  );

  const selectedTypes = escopos.map((e) => e.tipo);

  return (
    <div>
      <h2 className="text-xl font-bold text-primary mb-2">
        2. Delimitação do(s) Objeto(s) e Escopo(s)
      </h2>
      <p className="text-sm text-muted mb-6">
        Selecione os escopos aplicáveis. Para cada escopo selecionado, preencha
        os detalhes adicionais que aparecem (Contexto Inteligente).
      </p>

      <div className="space-y-3">
        {ESCOPO_TYPES.map((tipo) => {
          const isSelected = selectedTypes.includes(tipo);
          const escopoIdx = escopos.findIndex((e) => e.tipo === tipo);

          return (
            <div
              key={tipo}
              className={`border rounded-xl transition-all ${
                isSelected
                  ? "border-primary bg-primary-light/10 shadow-sm"
                  : "border-border bg-card"
              }`}
            >
              <div className="p-4">
                <Checkbox
                  label={ESCOPO_LABELS[tipo]}
                  checked={isSelected}
                  onChange={(checked) => toggleEscopo(tipo, checked)}
                />
              </div>

              {isSelected && escopoIdx >= 0 && (
                <div className="px-4 pb-4 border-t border-border/50 pt-4">
                  <EscopoDetails
                    escopo={escopos[escopoIdx]}
                    onUpdate={(partial) => updateEscopo(escopoIdx, partial)}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="bg-card border border-border rounded-xl p-4 mt-4">
        <Toggle
          label="Inserir Cláusula de Partes Relacionadas (2.4)?"
          value={incluirPartesRelacionadas}
          onChange={onChangePartesRelacionadas}
        />
        <p className="text-xs text-muted ml-14">
          Aplicável quando a contratação envolver hora trabalhada ou honorário mensal por processo.
        </p>
      </div>
    </div>
  );
}

function EscopoDetails({
  escopo,
  onUpdate,
}: {
  escopo: EscopoItem;
  onUpdate: (partial: Partial<EscopoItem>) => void;
}) {
  const { tipo } = escopo;
  const genericDetailLabel = GENERIC_DETAIL_LABELS[tipo];

  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-accent">
        Contexto Inteligente - Preencha os detalhes
      </p>

      {genericDetailLabel && (
        <FormField label={genericDetailLabel}>
          <TextArea
            value={escopo.descricao_custom || ""}
            onChange={(e) => onUpdate({ descricao_custom: e.target.value })}
            placeholder="Descreva os pontos principais, limites do escopo e informacoes relevantes..."
          />
        </FormField>
      )}

      {(tipo === "contencioso_representacao" ||
        tipo === "contencioso_tutela_urgencia") && (
        <>
          <FormField label="Número dos autos" hint="Caso aplicável, informe o número do processo">
            <Input
              value={escopo.numero_autos || ""}
              onChange={(e) => onUpdate({ numero_autos: e.target.value })}
              placeholder="0000000-00.0000.0.00.0000"
            />
          </FormField>
          {tipo === "contencioso_representacao" && (
            <FormField
              label="Demandas a ajuizar"
              hint="Caso seja para ajuizamento de novas demandas"
            >
              <TextArea
                value={escopo.demandas || ""}
                onChange={(e) => onUpdate({ demandas: e.target.value })}
                placeholder="Descreva as demandas..."
              />
            </FormField>
          )}
        </>
      )}

      {tipo === "contencioso_memoriais" && (
        <>
          <FormField label="Número dos autos">
            <Input
              value={escopo.numero_autos || ""}
              onChange={(e) => onUpdate({ numero_autos: e.target.value })}
              placeholder="0000000-00.0000.0.00.0000"
            />
          </FormField>
          <div className="bg-white rounded-lg p-3 border border-border/50">
            <p className="text-sm font-medium mb-2">
              Selecione as atividades aplicáveis:
            </p>
            <div className="space-y-1">
              <Checkbox
                label="Elaboração de Memoriais"
                checked={
                  escopo.subtipo_memoriais?.elaboracao_memoriais || false
                }
                onChange={(v) =>
                  onUpdate({
                    subtipo_memoriais: {
                      ...(escopo.subtipo_memoriais || {
                        elaboracao_memoriais: false,
                        despacho_memoriais: false,
                        sustentacao_oral_relator: false,
                        sustentacao_oral_todos_julgadores: false,
                      }),
                      elaboracao_memoriais: v,
                    },
                  })
                }
              />
              <Checkbox
                label="Despacho de Memoriais"
                checked={
                  escopo.subtipo_memoriais?.despacho_memoriais || false
                }
                onChange={(v) =>
                  onUpdate({
                    subtipo_memoriais: {
                      ...(escopo.subtipo_memoriais || {
                        elaboracao_memoriais: false,
                        despacho_memoriais: false,
                        sustentacao_oral_relator: false,
                        sustentacao_oral_todos_julgadores: false,
                      }),
                      despacho_memoriais: v,
                    },
                  })
                }
              />
              <Checkbox
                label="Sustentação oral com o Relator"
                checked={
                  escopo.subtipo_memoriais?.sustentacao_oral_relator || false
                }
                onChange={(v) =>
                  onUpdate({
                    subtipo_memoriais: {
                      ...(escopo.subtipo_memoriais || {
                        elaboracao_memoriais: false,
                        despacho_memoriais: false,
                        sustentacao_oral_relator: false,
                        sustentacao_oral_todos_julgadores: false,
                      }),
                      sustentacao_oral_relator: v,
                    },
                  })
                }
              />
              <Checkbox
                label="Sustentação oral com todos os julgadores"
                checked={
                  escopo.subtipo_memoriais
                    ?.sustentacao_oral_todos_julgadores || false
                }
                onChange={(v) =>
                  onUpdate({
                    subtipo_memoriais: {
                      ...(escopo.subtipo_memoriais || {
                        elaboracao_memoriais: false,
                        despacho_memoriais: false,
                        sustentacao_oral_relator: false,
                        sustentacao_oral_todos_julgadores: false,
                      }),
                      sustentacao_oral_todos_julgadores: v,
                    },
                  })
                }
              />
            </div>
          </div>
        </>
      )}

      {tipo === "consultoria_planejamento_patrimonial" && (
        <FormField
          label="Pessoas e patrimônios"
          hint="Especifique as pessoas e patrimônios envolvidos"
        >
          <TextArea
            value={escopo.pessoas_patrimonios || ""}
            onChange={(e) =>
              onUpdate({ pessoas_patrimonios: e.target.value })
            }
            placeholder="Descreva as pessoas e patrimônios..."
          />
        </FormField>
      )}

      {tipo === "consultoria_estruturacao_societaria" && (
        <FormField
          label="Tipo de reestruturação"
          hint="Fusão, cisão, aquisição, M&A, reorganização societária, etc."
        >
          <Input
            value={escopo.tipo_reestruturacao || ""}
            onChange={(e) =>
              onUpdate({ tipo_reestruturacao: e.target.value })
            }
            placeholder="Ex: Fusão entre empresas X e Y"
          />
        </FormField>
      )}

      {tipo === "consultoria_elaboracao_documentos" && (
        <FormField label="Documentos a elaborar" required>
          <TextArea
            value={escopo.documentos || ""}
            onChange={(e) => onUpdate({ documentos: e.target.value })}
            placeholder="Liste os documentos a serem elaborados..."
            required
          />
        </FormField>
      )}

      {tipo === "consultoria_opiniao_legal" && (
        <FormField label="Consulta / Tema do parecer" required>
          <TextArea
            value={escopo.consulta || ""}
            onChange={(e) => onUpdate({ consulta: e.target.value })}
            placeholder="Descreva a consulta ou tema do parecer..."
            required
          />
        </FormField>
      )}

      {tipo === "outro" && (
        <FormField label="Descrição do escopo" required>
          <TextArea
            value={escopo.descricao_custom || ""}
            onChange={(e) => onUpdate({ descricao_custom: e.target.value })}
            placeholder="Descreva o escopo detalhadamente..."
            required
          />
        </FormField>
      )}
    </div>
  );
}
