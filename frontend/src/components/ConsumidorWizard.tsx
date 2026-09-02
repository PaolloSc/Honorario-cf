"use client";

import StepCaso from "@/components/consumidor/StepCaso";
import StepEnvio from "@/components/consumidor/StepEnvio";
import StepPartes from "@/components/consumidor/StepPartes";
import StepIndicator from "@/components/ui/StepIndicator";
import {
  emailContato,
  formVazio,
  TIPO_CONSUMIDOR_AEREO,
  valorMilheiro,
  type ConsumidorFormData,
  type ContratanteConsumidor,
} from "@/types/consumidor";
import { useState } from "react";

const STEPS = [
  { id: 1, title: "Contratante" },
  { id: 2, title: "Caso" },
  { id: 3, title: "Envio" },
];

function normalize(data?: Partial<ConsumidorFormData> | null): ConsumidorFormData {
  const base = formVazio();
  if (!data) return base;
  return {
    ...base,
    ...data,
    tipo_contrato: TIPO_CONSUMIDOR_AEREO,
    contratantes: data.contratantes?.length ? data.contratantes : base.contratantes,
  };
}

function isEmail(valor: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(valor.trim());
}

function isCPF(cpf: string): boolean {
  const d = cpf.replace(/\D/g, "");
  if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false;
  for (const [len, mult] of [[9, 10], [10, 11]] as const) {
    let soma = 0;
    for (let i = 0; i < len; i++) soma += parseInt(d[i]) * (mult - i);
    let dv = 11 - (soma % 11);
    if (dv >= 10) dv = 0;
    if (parseInt(d[len]) !== dv) return false;
  }
  return true;
}

function validar(step: number, data: ConsumidorFormData): string[] {
  const erros: string[] = [];

  if (step === 1) {
    data.contratantes.forEach((c, i) => {
      const label = `Contratante ${i + 1}`;

      if (c.tipo === "PJ") {
        if (c.cnpj.replace(/\D/g, "").length !== 14) erros.push(`${label}: CNPJ inválido.`);
        if (!c.razao_social.trim()) erros.push(`${label}: informe a razão social.`);
        if (!c.endereco.trim()) erros.push(`${label}: informe o endereço da sede.`);
        if (!c.representante_nome.trim()) {
          erros.push(`${label}: informe o nome do representante legal.`);
        }
        if (!isCPF(c.representante_cpf)) {
          erros.push(`${label}: CPF do representante inválido.`);
        }
        if (emailContato(c) && !isEmail(emailContato(c))) {
          erros.push(`${label}: e-mail do representante inválido.`);
        }
        return;
      }

      if (!c.nome.trim()) erros.push(`${label}: informe o nome completo.`);
      if (!isCPF(c.cpf)) erros.push(`${label}: CPF inválido.`);
      if (c.email && !isEmail(c.email)) {
        erros.push(`${label}: e-mail inválido.`);
      }
      // O endereco e' montado pelo CEP — aponte o campo que o usuario preenche.
      if (!c.endereco.trim()) erros.push(`${label}: busque o CEP para montar o endereço.`);
      else if (!c.numero?.trim()) erros.push(`${label}: informe o número do endereço.`);
    });
  }

  if (step === 2) {
    if (data.res.length === 0) erros.push("Adicione pelo menos uma companhia aérea.");
    data.res.forEach((re, i) => {
      const label = data.res.length > 1 ? `Companhia ${i + 1}` : "Companhia";
      if (!re.companhia) erros.push(`${label}: selecione a companhia aérea.`);
      const milheiro = valorMilheiro(re);
      if (!milheiro || milheiro <= 0) erros.push(`${label}: informe o valor do milheiro.`);
      if (!re.razao_social.trim()) erros.push(`${label}: informe a razão social da Ré.`);
      if (re.cnpj.replace(/\D/g, "").length !== 14) {
        erros.push(`${label}: informe um CNPJ válido.`);
      }
    });
    if (!data.juizado.trim()) erros.push("Informe o juízo competente.");
    if (!data.prazo_pagamento_dias || data.prazo_pagamento_dias < 1) {
      erros.push("Informe o prazo de pagamento em dias.");
    }
    if (!data.comarca.trim()) erros.push("Informe a comarca.");
  }

  return erros;
}

interface Props {
  initialData?: Partial<ConsumidorFormData>;
  editContractId?: string;
  onSaveComplete?: (contractId: string) => void;
}

export default function ConsumidorWizard({
  initialData,
  editContractId,
  onSaveComplete,
}: Props = {}) {
  const [step, setStep] = useState(1);
  const [data, setData] = useState<ConsumidorFormData>(normalize(initialData));
  const [erros, setErros] = useState<string[]>([]);

  const patch = (p: Partial<ConsumidorFormData>) => {
    setErros([]);
    setData((prev) => ({ ...prev, ...p }));
  };

  const setContratantes = (contratantes: ContratanteConsumidor[]) => {
    setErros([]);
    setData((prev) => ({ ...prev, contratantes }));
  };

  const primeiroInvalidoAntes = (alvo: number): { step: number; erros: string[] } | null => {
    for (let s = 1; s < alvo; s++) {
      const e = validar(s, data);
      if (e.length) return { step: s, erros: e };
    }
    return null;
  };

  const irPara = (alvo: number) => {
    const invalido = primeiroInvalidoAntes(alvo);
    if (invalido) {
      setErros(invalido.erros);
      setStep(invalido.step);
      return;
    }
    setErros([]);
    setStep(alvo);
  };

  const errosAtuais = validar(step, data);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="text-center mb-8">
        <h1 className="font-display text-2xl font-semibold text-primary-dark tracking-wide">
          {editContractId ? "Editar Contrato" : "Novo Contrato — Ação de Consumo (Aérea)"}
        </h1>
        <p className="text-sm text-muted mt-1">
          {editContractId
            ? "Altere os dados e gere uma nova versão."
            : "Honorário de 25% do êxito, conforme modelo do escritório."}
        </p>
      </div>

      <StepIndicator steps={STEPS} currentStep={step} onStepClick={irPara} />

      <div className="mb-8">
        {step === 1 && (
          <StepPartes contratantes={data.contratantes} onChange={setContratantes} />
        )}
        {step === 2 && <StepCaso data={data} onChange={patch} />}
        {step === 3 && (
          <StepEnvio
            data={data}
            editContractId={editContractId}
            onSaveComplete={onSaveComplete}
          />
        )}
      </div>

      {erros.length > 0 && (
        <div className="mb-6 rounded-lg border border-danger bg-danger/[0.08] p-4 text-sm text-danger">
          <p className="font-semibold mb-2">Preencha os campos obrigatórios antes de avançar:</p>
          <ul className="list-disc list-inside space-y-1">
            {erros.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex justify-between items-center">
        <button
          type="button"
          onClick={() => step > 1 && irPara(step - 1)}
          disabled={step === 1}
          className="px-6 py-2.5 border border-border text-foreground rounded-lg font-medium hover:bg-background transition disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Anterior
        </button>

        <span className="text-sm text-muted">
          Etapa {step} de {STEPS.length}
        </span>

        {step < STEPS.length ? (
          <button
            type="button"
            onClick={() => irPara(step + 1)}
            disabled={errosAtuais.length > 0}
            title={errosAtuais[0]}
            className="px-6 py-2.5 bg-primary text-white rounded-lg font-medium hover:bg-primary-dark transition disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Próximo
          </button>
        ) : (
          <div />
        )}
      </div>
    </div>
  );
}
