"use client";
 
import Step1Contratante from "@/components/steps/Step1Contratante";
import Step2Escopo from "@/components/steps/Step2Escopo";
import Step3Honorarios from "@/components/steps/Step3Honorarios";
import Step4Acessorios from "@/components/steps/Step4Acessorios";
import Step5Participacao from "@/components/steps/Step5Participacao";
import Step6Revisao from "@/components/steps/Step6Revisao";
import Step7Envio, { type RevisaoSalva } from "@/components/steps/Step7Envio";
import StepIndicator from "@/components/ui/StepIndicator";
import type {
  Acessorios,
  Contratante,
  ContratoFormData,
  EscopoItem,
  Participacao,
} from "@/types/contract";
import RascunhosPendentes from "@/components/RascunhosPendentes";
import { validateEscopos, validateAcessorios, validateParticipacao } from "@/app/lib/validacaoPassos";
import { validateHonorarios } from "@/app/lib/validacaoHonorarios";
import { useRascunhoAutosave } from "@/components/useRascunhoAutosave";
import { getContractFormData } from "@/app/lib/api";
import { primeiraEtapaInvalidaAntes, retomarRascunho } from "@/app/lib/rascunho";
import { armazemReal } from "@/app/lib/rascunhoArmazem";
import { cnpjValido } from "@/app/lib/cnpj";
import { validarContratantes } from "@/app/lib/validarContratantes";
import { prepararModelo, type ModoModelo } from "@/app/lib/modeloContrato";
import { dataDaApi } from "@/app/lib/datas";
import { lerLocal, useDonoRascunho } from "@/app/lib/rascunhoLocal";
import { useAuthStatus } from "@/app/lib/useAuthStatus";
import { DADOS_INICIAIS, normalizarFormData } from "@/app/lib/estadoWizard";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
 
const STEPS = [
  { id: 1, title: "Contratante" },
  { id: 2, title: "Escopo" },
  { id: 3, title: "Honorários" },
  { id: 4, title: "Acessórios" },
  { id: 5, title: "Ficha Interna" },
  { id: 6, title: "Revisão" },
  { id: 7, title: "Envio" },
];
 
const INITIAL_JSON = JSON.stringify(DADOS_INICIAIS);

function novoIdRascunho(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
}

// Edição salva rascunho num id fixo por contrato: reabrir a edição acha o que ficou.
function idRascunhoEdicao(contractId: string): string {
  return `edit-${contractId}`;
}

function horaBrasilia(d: Date): string {
  return d.toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo", hour: "2-digit", minute: "2-digit" });
}

function validateStep(step: number, data: ContratoFormData): string[] {
  switch (step) {
    case 1:
      return validarContratantes(data, cnpjValido);
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
  const r = primeiraEtapaInvalidaAntes(step, data, validateStep);
  return r && { step: r.etapa, errors: r.erros };
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
  const [formData, setFormData] = useState<ContratoFormData>(normalizarFormData(initialData));
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  // Erros vindos da etapa 7 (422 do servidor): outro título no aviso enquanto forem eles na tela
  // (mesma lista; qualquer outra validação troca a lista e volta o título normal).
  const [errosDoServidor, setErrosDoServidor] = useState<string[] | null>(null);
  const currentStepErrors = validateStep(currentStep, formData);
  const canGoNext = currentStepErrors.length === 0;

  // ── Rascunho (autosave) — ao criar e ao editar (id fixo "edit-<contrato>") ──
  const authStatus = useAuthStatus();
  const dono = useDonoRascunho();
  const [draftId, setDraftId] = useState(() => (editContractId ? idRascunhoEdicao(editContractId) : novoIdRascunho()));
  // Na edição o formulário já nasce cheio: só há o que salvar depois de mudar algo.
  const [jsonInicial] = useState(() => (editContractId ? JSON.stringify(normalizarFormData(initialData)) : INITIAL_JSON));
  const [restaurando, setRestaurando] = useState(false);
  const [avisoRetomada, setAvisoRetomada] = useState("");
  const retomadaFeita = useRef(false);
  const temConteudo = useMemo(() => JSON.stringify(formData) !== jsonInicial, [formData, jsonInicial]);
  const autosave = useRascunhoAutosave({
    ativo: !restaurando,
    draftId,
    formData: formData as unknown as Record<string, unknown>,
    step: currentStep,
    temConteudo,
    dono,
  });
  const retomarAutosave = autosave.retomar;

  useEffect(() => {
    if (retomadaFeita.current) return;
    const id = editContractId
      ? idRascunhoEdicao(editContractId)
      : new URLSearchParams(window.location.search).get("rascunho");
    if (!id) {
      retomadaFeita.current = true;
      return;
    }
    setRestaurando(true);
    if (authStatus !== "authenticated") return; // espera a sessão para chamar a API
    retomadaFeita.current = true;

    (async () => {
      // só a cópia de quem está logado: a de outra pessoa nunca é aplicada (armazemReal)
      const r = await retomarRascunho(id, armazemReal(dono));
      if (r) {
        setDraftId(id);
        setFormData(normalizarFormData(r.dados as Partial<ContratoFormData>));
        setCurrentStep(r.passo); // volta na etapa exata, até a 7
        // a revisão por IA e a prévia não vão no rascunho: ao reabrir na 6/7 elas são refeitas
        if (r.passo >= 6) setAvisoRevisao("Rascunho retomado: a revisão por IA da sessão anterior não vale mais e foi refeita com os dados atuais.");
        retomarAutosave(r.versaoServidor);
        setAvisoRetomada(
          editContractId
            ? "Havia alterações desta edição que não viraram versão — foram retomadas. Confira, ou descarte para voltar ao contrato salvo."
            : "Rascunho retomado — confira os dados e continue de onde parou.",
        );
      } else if (!editContractId) {
        // edição sem rascunho é o caso normal: nada a avisar
        setAvisoRetomada("Rascunho não encontrado — pode já ter virado contrato ou ter sido descartado.");
      }
      setRestaurando(false);
    })();
  }, [authStatus, dono, editContractId, retomarAutosave]);

  // "Usar como modelo" (/?modelo=<id>&modo=cliente|escopo): contrato novo, rascunho novo.
  const modeloFeito = useRef(false);
  useEffect(() => {
    if (editContractId || modeloFeito.current) return;
    const params = new URLSearchParams(window.location.search);
    const modeloId = params.get("modelo");
    if (!modeloId || params.get("rascunho")) {
      modeloFeito.current = true;
      return;
    }
    setRestaurando(true); // segura o autosave até o modelo entrar
    if (authStatus !== "authenticated") return;
    modeloFeito.current = true;
    const modo: ModoModelo = params.get("modo") === "escopo" ? "escopo" : "cliente";

    (async () => {
      try {
        const { form_data } = await getContractFormData(modeloId);
        const contratantes = form_data.contratantes as Array<{ nome?: string }> | undefined;
        const origem = contratantes?.map((c) => c.nome?.trim()).filter(Boolean).join(", ") || "contrato anterior";
        setFormData(normalizarFormData(prepararModelo(form_data, modo) as Partial<ContratoFormData>));
        setAvisoRetomada(`Copiado de ${origem}, confira valores e datas.`);
        // recarregar a página não deve criar outro rascunho a partir do mesmo modelo
        window.history.replaceState(null, "", window.location.pathname);
      } catch (e) {
        setAvisoRetomada(`Não foi possível carregar o modelo: ${e instanceof Error ? e.message : "erro desconhecido"}`);
      } finally {
        setRestaurando(false);
      }
    })();
  }, [authStatus, editContractId]);

  const descartarRascunho = async () => {
    const pergunta = editContractId
      ? "Descartar as alterações não salvas e voltar ao contrato salvo? Não dá para desfazer."
      : "Descartar este rascunho e começar do zero? Não dá para desfazer.";
    if (!window.confirm(pergunta)) return;
    await autosave.descartar();
    setFormData(normalizarFormData(editContractId ? initialData : null));
    setCurrentStep(1);
    setDraftId(editContractId ? idRascunhoEdicao(editContractId) : novoIdRascunho());
    setAvisoRetomada("");
    autosave.retomar();
    if (!editContractId) window.history.replaceState(null, "", window.location.pathname);
  };

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
  const [revisaoSalva, setRevisaoSalva] = useState<RevisaoSalva | null>(null);
  const [avisoRevisao, setAvisoRevisao] = useState("");
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
        <div className="mt-2 text-xs" aria-live="polite">
          {autosave.estado === "salvando" && <span className="text-muted">Salvando rascunho…</span>}
          {autosave.estado === "salvo" && autosave.salvoEm && (
            <span className="text-primary-dark">
              {editContractId
                ? `Alterações guardadas como rascunho às ${horaBrasilia(autosave.salvoEm)} — ainda não são uma nova versão.`
                : `Rascunho salvo às ${horaBrasilia(autosave.salvoEm)} — você pode sair e retomar depois.`}{" "}
              <button type="button" onClick={() => void descartarRascunho()} className="underline text-muted hover:text-danger">
                Descartar
              </button>
            </span>
          )}
          {autosave.estado === "falhou" && (
            <span className="text-danger">
              Não foi possível salvar o rascunho no servidor — não feche esta página.{" "}
              <button type="button" onClick={() => void autosave.salvarAgora()} className="underline">
                Tentar de novo
              </button>
            </span>
          )}
          {autosave.estado === "conflito" && (
            <span className="text-danger">
              Este rascunho foi alterado em outra aba ou computador. O que você mudou aqui não está sendo salvo.{" "}
              <button
                type="button"
                onClick={() =>
                  editContractId
                    ? window.location.reload()
                    : window.location.assign(`/?rascunho=${encodeURIComponent(draftId)}`)
                }
                className="underline"
              >
                Abrir a versão mais recente
              </button>
            </span>
          )}
        </div>
      </div>

      {restaurando && <p className="mb-6 text-center text-sm text-muted">Carregando rascunho…</p>}
      {avisoRetomada && (
        <div className="mb-6 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm text-primary-dark">
          {avisoRetomada}
          {editContractId && (
            <>
              {" "}
              <button type="button" onClick={() => void descartarRascunho()} className="underline text-muted hover:text-danger">
                Descartar alterações
              </button>
            </>
          )}
        </div>
      )}
      {!editContractId && !restaurando && !temConteudo && <RascunhosPendentes />}

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
            onIrParaEtapa={(id, erros) => {
              const lista = erros ?? [];
              setValidationErrors(lista);
              setErrosDoServidor(lista);
              setCurrentStep(id);
            }}
            onContractGenerated={() => void autosave.descartar()}
            correcoesAplicadas={correcoesAplicadas}
            onCorrecoesAplicadasChange={setCorrecoesAplicadas}
            revisaoSalva={revisaoSalva}
            onRevisaoChange={setRevisaoSalva}
            avisoRevisao={avisoRevisao}
          />
        )}
      </div>

      {validationErrors.length > 0 && (
        <div className="mb-6 rounded-lg border border-danger bg-danger/[0.08] p-4 text-sm text-danger">
          <p className="font-semibold mb-2">
            {validationErrors === errosDoServidor
              ? "O contrato não foi gerado: corrija nesta etapa e volte ao Envio."
              : "Preencha os campos obrigatórios antes de avançar:"}
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
            // Nao desabilita: o clique mostra a lista do que falta (botao desabilitado nao dizia nada).
            aria-disabled={!canGoNext}
            title={!canGoNext ? currentStepErrors[0] : undefined}
            className={`px-6 py-2.5 bg-primary text-white rounded-lg font-medium hover:bg-primary-dark transition ${canGoNext ? "" : "opacity-50"}`}
          >
            Próximo
          </button>
        )}
        {currentStep === STEPS.length && <div />}
      </div>
    </div>
  );
}
