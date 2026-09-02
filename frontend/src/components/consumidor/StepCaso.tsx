"use client";

import { lookupCNPJ } from "@/app/lib/api";
import FormField, { Checkbox, Input, Select } from "@/components/ui/FormField";
import {
  detectarCompanhia,
  MILHEIRO_POR_COMPANHIA,
  reVazia,
  valorMilheiro,
  type ConsumidorFormData,
  type ReAerea,
} from "@/types/consumidor";
import { useRef, useState } from "react";

function formatCNPJ(value: string): string {
  return value
    .replace(/\D/g, "")
    .slice(0, 14)
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2}\.\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{2}\.\d{3}\.\d{3})(\d)/, "$1/$2")
    .replace(/^(\d{2}\.\d{3}\.\d{3}\/\d{4})(\d)/, "$1-$2");
}

const COMPANHIAS = Object.keys(MILHEIRO_POR_COMPANHIA).map((nome) => ({
  value: nome,
  label: `${nome} — milheiro R$ ${MILHEIRO_POR_COMPANHIA[nome].toFixed(2).replace(".", ",")}`,
}));

const SOMENTE_LEITURA = "bg-border/35 cursor-not-allowed text-muted";

function reais(v: number): string {
  return v.toFixed(2).replace(".", ",");
}

interface Props {
  data: ConsumidorFormData;
  onChange: (patch: Partial<ConsumidorFormData>) => void;
}

export default function StepCaso({ data, onChange }: Props) {
  const [buscando, setBuscando] = useState<number | null>(null);
  const [erroCNPJ, setErroCNPJ] = useState<Record<number, string>>({});
  // Companhia fora da tabela do milheiro: o usuario escolhe na mão.
  const [naoReconhecida, setNaoReconhecida] = useState<Record<number, boolean>>({});
  // Texto local por Ré: sem ele, apagar o milheiro caía de volta no valor da tabela.
  const [milheiroTexto, setMilheiroTexto] = useState<Record<number, string>>(() =>
    Object.fromEntries(
      data.res.map((re, i) => [i, valorMilheiro(re) === undefined ? "" : String(valorMilheiro(re))])
    )
  );

  // A lista mais recente: a consulta de CNPJ e' assincrona e o estado muda no meio.
  const atual = useRef(data.res);
  atual.current = data.res;

  const update = (i: number, partial: Partial<ReAerea>) => {
    onChange({ res: atual.current.map((re, idx) => (idx === i ? { ...re, ...partial } : re)) });
  };

  const buscarCNPJ = async (i: number, valor: string) => {
    const cnpj = formatCNPJ(valor);
    update(i, { cnpj });
    if (cnpj.replace(/\D/g, "").length !== 14) return;

    setBuscando(i);
    setErroCNPJ((prev) => ({ ...prev, [i]: "" }));
    try {
      const res = await lookupCNPJ(cnpj);
      // Contratos do escritorio trazem a razao social em caixa alta.
      const razao = res.razao_social.toUpperCase();
      // A companhia sai da propria razao social — o usuario so' confere.
      const detectada = detectarCompanhia(razao);
      const padrao = detectada ? MILHEIRO_POR_COMPANHIA[detectada] : undefined;
      if (padrao !== undefined) {
        setMilheiroTexto((prev) => ({ ...prev, [i]: String(padrao) }));
      }
      setNaoReconhecida((prev) => ({ ...prev, [i]: !detectada }));
      update(i, {
        cnpj,
        razao_social: razao,
        ...(detectada ? { companhia: detectada, valor_milheiro_override: undefined } : {}),
      });
    } catch (e) {
      setErroCNPJ((prev) => ({
        ...prev,
        [i]: `Não foi possível consultar o CNPJ (${
          e instanceof Error ? e.message : "erro"
        }). Digite a razão social manualmente.`,
      }));
    } finally {
      setBuscando(null);
    }
  };

  // Trocar de companhia repõe o valor da tabela (e limpa o ajuste manual).
  const trocarCompanhia = (i: number, companhia: string) => {
    const padrao = MILHEIRO_POR_COMPANHIA[companhia];
    setMilheiroTexto((prev) => ({ ...prev, [i]: padrao === undefined ? "" : String(padrao) }));
    update(i, { companhia, valor_milheiro_override: undefined });
  };

  const adicionarRe = () => {
    onChange({ res: [...data.res, reVazia()] });
  };

  const removerRe = (i: number) => {
    onChange({ res: data.res.filter((_, idx) => idx !== i) });
    setErroCNPJ((prev) => ({ ...prev, [i]: "" }));
    setNaoReconhecida((prev) => ({ ...prev, [i]: false }));
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Dados do caso</h2>
        <p className="text-sm text-muted mt-1">
          Honorário fixo de 25% do êxito e dados da contratada já estão no modelo.
        </p>
      </div>

      {data.res.map((re, i) => {
        const milheiro = valorMilheiro(re);
        const daTabela = MILHEIRO_POR_COMPANHIA[re.companhia];
        return (
          <div key={i} className="border border-border rounded-xl p-5">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-medium">
                Companhia aérea (Ré){data.res.length > 1 ? ` ${i + 1}` : ""}
              </h3>
              {data.res.length > 1 && (
                <button
                  type="button"
                  onClick={() => removerRe(i)}
                  className="text-sm text-danger hover:underline"
                >
                  Remover
                </button>
              )}
            </div>

            <FormField
              label="CNPJ da Ré"
              required
              hint="Identifica a companhia e preenche a razão social"
            >
              <div className="flex gap-2">
                <Input
                  value={re.cnpj}
                  onChange={(e) => buscarCNPJ(i, e.target.value)}
                  placeholder="00.000.000/0000-00"
                />
                {buscando === i && (
                  <span className="text-sm text-muted self-center">Buscando...</span>
                )}
              </div>
              {erroCNPJ[i] && <p className="text-xs text-danger mt-1">{erroCNPJ[i]}</p>}
            </FormField>

            {/* A companhia vem do CNPJ. A lista so' aparece quando nao foi reconhecida. */}
            {naoReconhecida[i] && (
              <FormField
                label="Companhia"
                required
                hint="Não reconheci a companhia por esse CNPJ — escolha na lista"
              >
                <Select
                  value={re.companhia}
                  onChange={(e) => trocarCompanhia(i, e.target.value)}
                  options={COMPANHIAS}
                  placeholder="Selecione a companhia"
                />
              </FormField>
            )}

            <FormField
              label="Valor do milheiro (R$)"
              required
              hint="Vem da tabela do escritório; ajuste aqui se este caso for diferente"
            >
              <Input
                type="number"
                step="0.01"
                min={0}
                value={milheiroTexto[i] ?? ""}
                onChange={(e) => {
                  setMilheiroTexto((prev) => ({ ...prev, [i]: e.target.value }));
                  update(i, {
                    valor_milheiro_override:
                      e.target.value === "" ? undefined : Number(e.target.value),
                  });
                }}
              />
            </FormField>

            {re.companhia && milheiro !== undefined && (
              <p className="text-sm text-primary-dark bg-primary/5 border border-primary rounded-lg px-3 py-2 mb-4">
                Linha na tabela do milheiro:{" "}
                <strong>
                  {re.companhia.toUpperCase()} — R$ {reais(milheiro)}
                </strong>
                {re.valor_milheiro_override !== undefined &&
                  re.valor_milheiro_override !== daTabela && (
                    <span className="block text-xs mt-1 text-muted">
                      Valor ajustado manualmente
                      {daTabela !== undefined ? ` (tabela: R$ ${reais(daTabela)})` : ""}
                    </span>
                  )}
              </p>
            )}

            <FormField
              label="Razão social da Ré"
              required
              hint="Preenchida pela consulta do CNPJ — vai assim na Cláusula II"
            >
              {/* So' libera a digitacao se a consulta falhar — senao o usuario trava. */}
              <Input
                value={re.razao_social}
                readOnly={!erroCNPJ[i]}
                tabIndex={erroCNPJ[i] ? undefined : -1}
                onChange={(e) => update(i, { razao_social: e.target.value.toUpperCase() })}
                className={erroCNPJ[i] ? "" : SOMENTE_LEITURA}
                placeholder="Preenchida pelo CNPJ"
              />
            </FormField>
          </div>
        );
      })}

      <button
        type="button"
        onClick={adicionarRe}
        className="px-4 py-2 border border-border rounded-lg text-sm font-medium hover:bg-background transition"
      >
        + Adicionar Companhia
      </button>

      <div className="border border-border rounded-xl p-5">
        <h3 className="font-medium mb-4">Processo e prazos</h3>

        <FormField label="Juízo" required>
          <Input
            value={data.juizado}
            onChange={(e) => onChange({ juizado: e.target.value })}
            placeholder="Juizado Especial Cível de Belo Horizonte - MG"
          />
        </FormField>

        <div className="grid grid-cols-2 gap-4 items-end">
          <FormField
            label="Prazo de pagamento (dias)"
            required
            hint="Após o recebimento dos valores/milhas"
          >
            <Input
              type="number"
              min={1}
              value={data.prazo_pagamento_dias}
              onChange={(e) => onChange({ prazo_pagamento_dias: Number(e.target.value) || 0 })}
            />
          </FormField>

          <FormField label="Comarca" required hint="Foro e cidade de assinatura">
            <Input
              value={data.comarca}
              onChange={(e) => onChange({ comarca: e.target.value })}
            />
          </FormField>
        </div>

        <FormField label="Data do contrato" hint="Vazio = data de hoje">
          <Input
            type="date"
            value={data.data_contrato ?? ""}
            onChange={(e) => onChange({ data_contrato: e.target.value })}
          />
        </FormField>

        <Checkbox
          label="A contratada elabora a reclamação (Reclame Aqui / consumidor.gov.br)"
          checked={data.elabora_reclamacao}
          onChange={(v) => onChange({ elabora_reclamacao: v })}
          hint="Desmarcado: o escritório apenas orienta o contratante a apresentá-la"
        />
      </div>
    </div>
  );
}
