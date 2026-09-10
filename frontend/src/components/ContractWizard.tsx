"use client";
 
import Step1Contratante from "@/components/steps/Step1Contratante";
import Step2Escopo from "@/components/steps/Step2Escopo";
import Step3Honorarios from "@/components/steps/Step3Honorarios";
import Step4Acessorios from "@/components/steps/Step4Acessorios";
import Step5Participacao from "@/components/steps/Step5Participacao";
import Step6Revisao from "@/components/steps/Step6Revisao";
import Step7Envio from "@/components/steps/Step7Envio";
import StepIndicator from "@/components/ui/StepIndicator";
import type {
  Acessorios,
  Contratante,
  ContratoFormData,
  EscopoItem,
  Participacao,
} from "@/types/contract";
import { useCallback, useEffect, useState } from "react";
 
const STEPS = [
  { id: 1, title: "Contratante" },
  { id: 2, title: "Escopo" },
  { id: 3, title: "Honorários" },
  { id: 4, title: "Acessórios" },
  { id: 5, title: "Ficha Interna" },
  { id: 6, title: "Revisão" },
  { id: 7, title: "Envio" },
];
 
const INITIAL_DATA: ContratoFormData = {
  contratantes: [
    {
      tipo: "PF",
      nome: "",
      nacionalidade: "Brasileiro(a)",
      cpf: "",
      profissao: "",
      estado_civil: "Solteiro(a)",
      endereco: "",
      email: "",
    },
  ],
  incluir_partes_relacionadas: false,
  escopos: [],
  acessorios: {
    tem_reembolso: true,
    reembolso_limitado: false,
    tem_penalidade_inadimplemento: true,
  },
  participacao: {
    tem_participacao: false,
  },
};

function normalizeFormData(data: Partial<ContratoFormData> | null | undefined): ContratoFormData {
  if (!data) return { ...INITIAL_DATA };

  return {
    contratantes: data.contratantes?.length ? data.contratantes : INITIAL_DATA.contratantes,
    incluir_partes_relacionadas: data.incluir_partes_relacionadas ?? false,
    escopos: data.escopos ?? [],
    acessorios: {
      tem_reembolso: data.acessorios?.tem_reembolso ?? true,
      reembolso_limitado: data.acessorios?.reembolso_limitado ?? false,
      descricao_limitacao_reembolso: data.acessorios?.descricao_limitacao_reembolso,
      tem_penalidade_inadimplemento: data.acessorios?.tem_penalidade_inadimplemento ?? true,
      valor_diligencia: data.acessorios?.valor_diligencia,
      valor_km: data.acessorios?.valor_km,
      criterio_extincao_exito: data.acessorios?.criterio_extincao_exito,
      clausulas_adicionais: data.acessorios?.clausulas_adicionais,
    },
    participacao: (() => {
      const p = (data.participacao ?? {}) as any;
      // Aceita lista, string legada ou ausência — contratos antigos gravaram string.
      const lista = (v: unknown): string[] =>
        Array.isArray(v) ? v : typeof v === "string" && v.trim() ? [v] : [];
      let valorTipo = p.valor_tipo;
      let valorOutro = p.valor_outro ?? "";
      if (!valorTipo && p.percentual_ou_valor) {
        valorTipo = "outro";
        valorOutro = p.percentual_ou_valor;
      }
      // Contratos antigos gravaram para_quem (lista de nomes) + uma natureza única —
      // migra para participantes (cada advogado com natureza/percentual próprios).
      const participantes = Array.isArray(p.participantes) && p.participantes.length
        ? p.participantes
        : lista(p.para_quem).map((nome) => ({
            nome,
            natureza: p.natureza ?? "",
            percentual: p.valor_percentual,
          }));
      return {
        tem_participacao: p.tem_participacao ?? false,
        valor_tipo: valorTipo,
        valor_percentual: p.valor_percentual ?? "",
        valor_monetario: p.valor_monetario,
        valor_outro: valorOutro,
        participantes,
        responsavel_captacao: p.responsavel_captacao ?? "",
        responsavel_gestao: p.responsavel_gestao ?? "",
        contato_financeiro_nome: p.contato_financeiro_nome ?? "",
        contato_financeiro_email: p.contato_financeiro_email ?? "",
        contato_financeiro_telefone: p.contato_financeiro_telefone ?? "",
        categoria_cliente: p.categoria_cliente ?? "",
        etiquetas: lista(p.etiquetas),
        listas_transmissao: lista(p.listas_transmissao),
        // Sem estes a base da participação sumia ao reabrir o contrato para edição.
        base_tipo: p.base_tipo,
        base_escopo_index: p.base_escopo_index,
        base_honorario: p.base_honorario,
        base_label: p.base_label ?? "",
      };
    })(),
    email_destinatario: data.email_destinatario,
  };
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function digits(value: string | undefined): string {
  return (value || "").replace(/\D/g, "");
}

function isEmail(value: string | undefined): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text(value));
}

function isValidCPF(cpf: string): boolean {
  const d = cpf.replace(/\D/g, "");
  if (d.length !== 11) return false;
  // Reject known invalid patterns (all same digit)
  if (/^(\d)\1{10}$/.test(d)) return false;
  // First check digit
  let sum = 0;
  for (let i = 0; i < 9; i++) sum += parseInt(d[i]) * (10 - i);
  let check = 11 - (sum % 11);
  if (check >= 10) check = 0;
  if (parseInt(d[9]) !== check) return false;
  // Second check digit
  sum = 0;
  for (let i = 0; i < 10; i++) sum += parseInt(d[i]) * (11 - i);
  check = 11 - (sum % 11);
  if (check >= 10) check = 0;
  if (parseInt(d[10]) !== check) return false;
  return true;
}

function validateContratantes(data: ContratoFormData): string[] {
  const errors: string[] = [];

  if (data.contratantes.length === 0) {
    errors.push("Adicione pelo menos um contratante.");
    return errors;
  }

  data.contratantes.forEach((contratante, index) => {
    const label = `Contratante ${index + 1}`;

    if (contratante.tipo === "PF") {
      if (!text(contratante.nome)) errors.push(`${label}: informe o nome completo.`);
      if (!isValidCPF(contratante.cpf)) errors.push(`${label}: CPF inválido.`);
      if (!text(contratante.estado_civil)) errors.push(`${label}: informe o estado civil.`);
      if (!isEmail(contratante.email)) errors.push(`${label}: informe um e-mail válido.`);
      if (!text(contratante.endereco)) errors.push(`${label}: informe o endereço completo.`);
      return;
    }

    if (digits(contratante.cnpj).length !== 14) errors.push(`${label}: informe um CNPJ com 14 dígitos.`);
    if (!isEmail(contratante.email)) errors.push(`${label}: informe um e-mail válido.`);
    if (!text(contratante.razao_social)) errors.push(`${label}: busque o CNPJ para preencher a Razão Social.`);
    if (!text(contratante.endereco)) errors.push(`${label}: busque o CNPJ para preencher o endereço.`);
  });

  return errors;
}

function validateEscopos(data: ContratoFormData): string[] {
  const errors: string[] = [];

  if (data.escopos.length === 0) {
    errors.push("Selecione pelo menos um escopo.");
    return errors;
  }

  data.escopos.forEach((escopo, index) => {
    const label = `Escopo ${index + 1}`;

    if (escopo.tipo === "consultoria_elaboracao_documentos" && !text(escopo.documentos)) {
      errors.push(`${label}: informe os documentos a elaborar.`);
    }

    if (escopo.tipo === "consultoria_opiniao_legal" && !text(escopo.consulta)) {
      errors.push(`${label}: informe a consulta ou tema do parecer.`);
    }

    if (escopo.tipo === "outro" && !text(escopo.descricao_custom)) {
      errors.push(`${label}: descreva o escopo.`);
    }
  });

  return errors;
}

function validateHonorarios(data: ContratoFormData): string[] {
  const errors: string[] = [];

  data.escopos.forEach((escopo, index) => {
    const label = `Escopo ${index + 1}`;

    if (escopo.honorarios.length === 0) {
      errors.push(`${label}: selecione pelo menos um tipo de honorário.`);
    }
  });

  return errors;
}

function validateAcessorios(_data: ContratoFormData): string[] {
  return [];
}

function validateParticipacao(_data: ContratoFormData): string[] {
  return [];
}

function validateStep(step: number, data: ContratoFormData): string[] {
  switch (step) {
    case 1:
      return validateContratantes(data);
    case 2:
      return validateEscopos(data);
    case 3:
      return validateHonorarios(data);
    case 4:
      return validateAcessorios(data);
    case 5:
      return validateParticipacao(data);
    default:
      return [];
  }
}

function firstInvalidStepBefore(step: number, data: ContratoFormData): {
  step: number;
  errors: string[];
} | null {
  for (let candidate = 1; candidate < step; candidate += 1) {
    const errors = validateStep(candidate, data);
    if (errors.length > 0) {
      return { step: candidate, errors };
    }
  }

  return null;
}
 
interface ContractWizardProps {
  initialData?: ContratoFormData;
  editContractId?: string;
  onSaveComplete?: (contractId: string) => void;
}

export default function ContractWizard({
  initialData,
  editContractId,
  onSaveComplete,
}: ContractWizardProps = {}) {
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState<ContratoFormData>(normalizeFormData(initialData));
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const currentStepErrors = validateStep(currentStep, formData);
  const canGoNext = currentStepErrors.length === 0;

  useEffect(() => {
    const invalidStep = firstInvalidStepBefore(currentStep, formData);
    if (!invalidStep) return;

    setValidationErrors(invalidStep.errors);
    setCurrentStep(invalidStep.step);
  }, [currentStep, formData]);
 
  const updateContratantes = useCallback(
    (contratantes: Contratante[]) => {
      setValidationErrors([]);
      setFormData((prev) => ({ ...prev, contratantes }));
    },
    []
  );
 
  const updatePartesRelacionadas = useCallback(
    (incluir_partes_relacionadas: boolean) => {
      setValidationErrors([]);
      setFormData((prev) => ({ ...prev, incluir_partes_relacionadas }));
    },
    []
  );
 
  // Histórico do que já foi corrigido na revisão por IA (Step 7). Fica aqui, e não
  // dentro do Step7Envio, porque esse componente desmonta ao trocar de passo — sem
  // isso, sair e voltar pro Step 7 resetava o histórico pra vazio.
  const [correcoesAplicadas, setCorrecoesAplicadas] = useState<Array<{ trecho: string; sugestao: string }>>([]);

  const updateEscopos = useCallback((escopos: EscopoItem[]) => {
    setValidationErrors([]);
    setFormData((prev) => ({ ...prev, escopos }));
  }, []);
 
  const updateAcessorios = useCallback((acessorios: Acessorios) => {
    setValidationErrors([]);
    setFormData((prev) => ({ ...prev, acessorios }));
  }, []);
 
  const updateParticipacao = useCallback((participacao: Participacao) => {
    setValidationErrors([]);
    setFormData((prev) => ({ ...prev, participacao }));
  }, []);
 
  const goNext = () => {
    const invalidStep = firstInvalidStepBefore(currentStep + 1, formData);
    if (invalidStep) {
      setValidationErrors(invalidStep.errors);
      setCurrentStep(invalidStep.step);
      return;
    }

    const errors = validateStep(currentStep, formData);
    if (errors.length > 0) {
      setValidationErrors(errors);
      return;
    }

    if (currentStep < STEPS.length) {
      setValidationErrors([]);
      setCurrentStep((s) => s + 1);
    }
  };
 
  const goPrev = () => {
    if (currentStep > 1) {
      setValidationErrors([]);
      setCurrentStep((s) => s - 1);
    }
  };
 
  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="text-center mb-8">
        <h1 className="font-display text-2xl font-semibold text-primary-dark tracking-wide">
          {editContractId ? "Editar Contrato" : "Novo Contrato de Honorários"}
        </h1>
        <p className="text-sm text-muted mt-1">
          {editContractId
            ? "Altere os dados e gere uma nova versão."
            : "Preencha as etapas abaixo para gerar o contrato."}
        </p>
      </div>
 
      <StepIndicator steps={STEPS} currentStep={currentStep} onStepClick={(id) => {
        const invalid = firstInvalidStepBefore(id, formData);
        if (invalid) {
          setValidationErrors(invalid.errors);
          setCurrentStep(invalid.step);
          return;
        }
        setValidationErrors([]);
        setCurrentStep(id);
      }} />
 
      {/* Step Content */}
      <div className="mb-8">
        {currentStep === 1 && (
          <Step1Contratante
            contratantes={formData.contratantes}
            onChange={updateContratantes}
          />
        )}
        {currentStep === 2 && (
          <Step2Escopo
            escopos={formData.escopos}
            onChange={updateEscopos}
            incluirPartesRelacionadas={formData.incluir_partes_relacionadas}
            onChangePartesRelacionadas={updatePartesRelacionadas}
          />
        )}
        {currentStep === 3 && (
          <Step3Honorarios
            escopos={formData.escopos}
            onChange={updateEscopos}
          />
        )}
        {currentStep === 4 && (
          <Step4Acessorios
            acessorios={formData.acessorios}
            onChange={updateAcessorios}
          />
        )}
        {currentStep === 5 && (
          <Step5Participacao
            participacao={formData.participacao}
            onChange={updateParticipacao}
            escopos={formData.escopos}
          />
        )}
        {currentStep === 6 && <Step6Revisao data={formData} />}
        {currentStep === 7 && (
          <Step7Envio
            data={formData}
            editContractId={editContractId}
            onSaveComplete={onSaveComplete}
            onDataChange={setFormData}
            correcoesAplicadas={correcoesAplicadas}
            onCorrecoesAplicadasChange={setCorrecoesAplicadas}
          />
        )}
      </div>

      {validationErrors.length > 0 && (
        <div className="mb-6 rounded-lg border border-danger bg-danger/[0.08] p-4 text-sm text-danger">
          <p className="font-semibold mb-2">
            Preencha os campos obrigatórios antes de avançar:
          </p>
          <ul className="list-disc list-inside space-y-1">
            {validationErrors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      )}
 
      {/* Navigation */}
      <div className="flex justify-between items-center">
        <button
          type="button"
          onClick={goPrev}
          disabled={currentStep === 1}
          className="px-6 py-2.5 border border-border text-foreground rounded-lg font-medium hover:bg-background transition disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Anterior
        </button>
 
        <span className="text-sm text-muted">
          Etapa {currentStep} de {STEPS.length}
        </span>
 
        {currentStep < STEPS.length && (
          <button
            type="button"
            onClick={goNext}
            disabled={!canGoNext}
            title={!canGoNext ? currentStepErrors[0] : undefined}
            className="px-6 py-2.5 bg-primary text-white rounded-lg font-medium hover:bg-primary-dark transition disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Próximo
          </button>
        )}
        {currentStep === STEPS.length && <div />}
      </div>
    </div>
  );
}
