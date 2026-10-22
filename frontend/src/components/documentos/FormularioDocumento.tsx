"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  gerarDocumento,
  listDocumentos,
  prefillDocumento,
  previewDocumento,
  substabelecimentoExistente,
  updateContract,
  type PrefillDocumento,
  type SubstabelecimentoExistente,
} from "@/app/lib/api";
import { cnpjValido } from "@/app/lib/cnpj";
import { hojeBrasilia } from "@/app/lib/datas";
import {
  ROTULO_TIPO,
  errosDaApi,
  estadoDoFormData,
  estadoInicial,
  montarPayload,
  validar,
  type AditivoForm,
  type DistratoForm,
  type Erros,
  type EstadoDocumento,
  type SubstabelecimentoForm,
  type TipoDocumento,
} from "@/app/lib/documentos";
import { useAuthStatus } from "@/app/lib/useAuthStatus";
import { CamposAditivo, CamposDistrato, CamposSubstabelecimento } from "./Campos";

interface Props {
  tipo: TipoDocumento;
  /** Contrato de origem (obrigatório para aditivo e distrato; opcional no substabelecimento). */
  origemId: string | null;
  /** Edição de rascunho: grava nova versão no lugar de criar outro documento. */
  editContractId?: string;
  initialFormData?: Record<string, unknown>;
}

const botaoPrimario = "px-5 py-2.5 rounded-lg bg-primary-dark text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed";
const botaoSecundario = "px-5 py-2.5 rounded-lg border border-border text-sm text-foreground hover:bg-background disabled:opacity-50";

function nomeDoc(c: Record<string, unknown>): string {
  const nome = String(c.razao_social ?? c.nome ?? "");
  const doc = String(c.cnpj ?? c.cpf ?? "");
  return doc ? `${nome} — ${doc}` : nome;
}

export default function FormularioDocumento({ tipo, origemId, editContractId, initialFormData }: Props) {
  const router = useRouter();
  const sessionStatus = useAuthStatus();
  const editando = !!editContractId;
  const rotulo = ROTULO_TIPO[tipo];

  const [estado, setEstado] = useState<EstadoDocumento>(() =>
    initialFormData ? estadoDoFormData(tipo, initialFormData, hojeBrasilia()) : estadoInicial(tipo, hojeBrasilia()),
  );
  const [prefill, setPrefill] = useState<PrefillDocumento | null>(null);
  const [carregando, setCarregando] = useState(!!origemId && !editando);
  const [distratoExistente, setDistratoExistente] = useState(false);
  const [erros, setErros] = useState<Erros>({});
  const [geral, setGeral] = useState("");
  const [previa, setPrevia] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  // Substabelecimento: o mesmo cliente (CPF/CNPJ) já tem um? Padrão: acrescentar o processo a ele.
  const [existente, setExistente] = useState<SubstabelecimentoExistente | null>(null);
  const [acrescentar, setAcrescentar] = useState(true);
  const docOutorgante = tipo === "substabelecimento" ? (estado as SubstabelecimentoForm).outorgante_documento : "";
  const docDigitos = docOutorgante.replace(/\D/g, "");

  useEffect(() => {
    if (tipo !== "substabelecimento" || editando || sessionStatus !== "authenticated" || ![11, 14].includes(docDigitos.length)) {
      setExistente(null);
      return;
    }
    let ativo = true;
    substabelecimentoExistente(docDigitos)
      .then((r) => ativo && setExistente(r.existe ? r : null))
      .catch(() => ativo && setExistente(null));
    return () => {
      ativo = false;
    };
  }, [tipo, editando, sessionStatus, docDigitos]);

  const acrescentando = !!existente?.pode_acrescentar && acrescentar;

  // Ao acrescentar, as partes e o endereço do documento existente já vêm preenchidos (o que for
  // informado aqui substitui o de lá).
  useEffect(() => {
    if (!acrescentando || !existente) return;
    const doc = estadoDoFormData("substabelecimento", { ...existente }, "") as SubstabelecimentoForm;
    setEstado((atual) => ({
      ...(atual as SubstabelecimentoForm),
      substabelecentes: doc.substabelecentes,
      substabelecidos: doc.substabelecidos,
      endereco_substabelecidos: doc.endereco_substabelecidos,
    }));
  }, [acrescentando, existente]);

  // Pré-preenchimento pelo contrato de origem (partes só leitura; data do contrato editável).
  useEffect(() => {
    if (sessionStatus !== "authenticated" || !origemId || editando) return;
    let ativo = true;
    (async () => {
      try {
        const [p, docs] = await Promise.all([
          prefillDocumento(origemId),
          tipo === "distrato" ? listDocumentos(origemId) : Promise.resolve(null),
        ]);
        if (!ativo) return;
        setPrefill(p);
        setDistratoExistente(!!docs?.documentos.some((d) => d.tipo_contrato === "distrato" && d.status !== "cancelado"));
        setEstado((atual) => {
          if (tipo === "substabelecimento") {
            const c = p.contratantes[0];
            if (!c) return atual;
            return {
              ...(atual as SubstabelecimentoForm),
              outorgante_pj: !!c.cnpj,
              outorgante_nome: String(c.razao_social ?? c.nome ?? ""),
              outorgante_documento: String(c.cnpj ?? c.cpf ?? ""),
            };
          }
          const a = atual as AditivoForm | DistratoForm;
          return a.data_contrato_origem ? atual : { ...a, data_contrato_origem: p.data_contrato_origem ?? "" };
        });
      } catch (e) {
        if (ativo) setGeral(errosDaApi(e).geral);
      } finally {
        if (ativo) setCarregando(false);
      }
    })();
    return () => {
      ativo = false;
    };
  }, [sessionStatus, origemId, tipo, editando]);

  const voltarPara = editContractId ? `/contracts/${editContractId}` : origemId ? `/contracts/${origemId}` : "/contracts";

  const aplicarErroDaApi = (e: unknown) => {
    const r = errosDaApi(e);
    setErros(r.campos);
    setGeral(r.geral || (Object.keys(r.campos).length ? "Corrija os campos destacados." : ""));
  };

  const conferir = (): Record<string, unknown> | null => {
    const e = validar(tipo, estado, cnpjValido);
    setErros(e);
    setGeral(Object.keys(e).length ? "Corrija os campos destacados." : "");
    return Object.keys(e).length ? null : montarPayload(tipo, estado, origemId);
  };

  const verPrevia = async () => {
    const payload = conferir();
    if (!payload) return;
    setOcupado(true);
    try {
      setPrevia(await previewDocumento(tipo, payload));
    } catch (e) {
      aplicarErroDaApi(e);
    } finally {
      setOcupado(false);
    }
  };

  const gerar = async () => {
    const payload = conferir();
    if (!payload) return;
    setOcupado(true);
    try {
      const r = await gerarDocumento(tipo, payload, acrescentando ? existente?.contract_id : undefined);
      router.push(`/contracts/${r.contract_id}`);
    } catch (e) {
      aplicarErroDaApi(e);
      setPrevia(null); // volta ao formulário com o erro à vista
    } finally {
      setOcupado(false);
    }
  };

  const salvarEdicao = async () => {
    const payload = conferir();
    if (!payload || !editContractId) return;
    setOcupado(true);
    try {
      await updateContract(editContractId, { ...(initialFormData ?? {}), ...payload });
      router.push(`/contracts/${editContractId}`);
    } catch (e) {
      aplicarErroDaApi(e);
    } finally {
      setOcupado(false);
    }
  };

  if (carregando) {
    return <div className="max-w-3xl mx-auto px-4 py-12 text-center text-muted">Carregando contrato original...</div>;
  }

  const bloqueado = tipo === "distrato" && distratoExistente;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Na edicao a pagina ja mostra "Voltar ao contrato". */}
      {!editando && (
        <a href={voltarPara} className="text-sm text-muted hover:text-foreground transition inline-block mb-2">&larr; Voltar</a>
      )}
      <h1 className="font-display text-xl font-semibold text-primary-dark tracking-wide mb-1">
        {editando ? `Editar ${rotulo.toLowerCase()}` : `Novo ${rotulo.toLowerCase()}`}
      </h1>
      {tipo === "substabelecimento" && !origemId && !editando && (
        <p className="text-sm text-muted mb-4">Sem contrato original: informe o cliente (outorgante) abaixo.</p>
      )}

      {prefill && !editando && (
        <div className="rounded-lg border border-border bg-card p-4 mb-4 text-sm">
          <p className="font-medium text-foreground mb-1">
            {tipo === "substabelecimento" ? "Cliente do contrato original" : "Partes (do contrato original)"}
          </p>
          <ul className="text-muted">
            {prefill.contratantes.map((c, i) => <li key={i}>{nomeDoc(c)}</li>)}
            <li>CARVALHO &amp; FURTADO ADVOGADOS — 25.463.159/0001-73</li>
          </ul>
          {tipo === "aditivo" && (
            <p className="text-muted mt-1">Este será o {prefill.aditivos_existentes + 1}º aditivo do contrato.</p>
          )}
        </div>
      )}

      {prefill?.aviso && !editando && (
        <div role="status" className="rounded-lg border border-warning bg-warning/[0.08] p-3 mb-4 text-sm text-warning">
          {prefill.aviso} Você pode continuar, mas confira se o documento faz sentido.
        </div>
      )}
      {bloqueado && (
        <div role="alert" className="rounded-lg border border-danger bg-danger/[0.08] p-3 mb-4 text-sm text-danger">
          Já existe um distrato para este contrato. Abra-o na página do contrato.
        </div>
      )}
      {geral && (
        <div role="alert" className="rounded-lg border border-danger bg-danger/[0.08] p-3 mb-4 text-sm text-danger">{geral}</div>
      )}

      {previa !== null ? (
        <>
          <p className="text-sm text-muted mb-2">Confira o texto. O documento só é gerado depois desta prévia.</p>
          {acrescentando && (
            <p role="note" className="rounded-lg border border-warning bg-warning/[0.08] p-3 mb-3 text-sm text-warning">
              Ao gerar, o(s) processo(s) abaixo serão acrescentados ao substabelecimento que este cliente já tem (nova versão do mesmo documento).
            </p>
          )}
          {tipo === "substabelecimento" && (
            <p role="note" className="rounded-lg border border-border bg-card p-3 mb-3 text-sm text-foreground">
              Assinatura preferencialmente com o token do advogado, por sócio com poderes conforme o contrato social. Em caso de urgência ou indisponibilidade, use o procedimento alternativo do escritório.
              <span className="block text-muted mt-1">Depois de gerar, use &quot;Baixar DOCX&quot; na página do documento para imprimir ou assinar direto. O envio pelo DocuSeal é opcional.</span>
            </p>
          )}
          <div className="mb-4 border border-border rounded-xl overflow-hidden bg-white">
            <iframe srcDoc={previa} title={`Prévia do ${rotulo.toLowerCase()}`} sandbox="" className="w-full" style={{ height: "65vh" }} />
          </div>
          <div className="flex flex-wrap gap-3">
            <button type="button" className={botaoSecundario} onClick={() => setPrevia(null)} disabled={ocupado}>Voltar e editar</button>
            <button type="button" className={botaoPrimario} onClick={gerar} disabled={ocupado || bloqueado}>
              {ocupado ? "Gerando..." : `Gerar ${rotulo.toLowerCase()}`}
            </button>
          </div>
        </>
      ) : (
        <div className="bg-card rounded-xl border border-border p-5">
          {tipo === "aditivo" && <CamposAditivo estado={estado as AditivoForm} onChange={setEstado} erros={erros} />}
          {tipo === "distrato" && <CamposDistrato estado={estado as DistratoForm} onChange={setEstado} erros={erros} />}
          {tipo === "substabelecimento" && <CamposSubstabelecimento estado={estado as SubstabelecimentoForm} onChange={setEstado} erros={erros} />}

          {existente && (
            <div role="group" aria-label="Substabelecimento já existente deste cliente" className="mt-5 rounded-lg border border-warning bg-warning/[0.08] p-4 text-sm">
              {existente.pode_acrescentar ? (
                <>
                  <p className="font-medium text-foreground mb-2">
                    Este cliente já tem substabelecimento
                    {existente.processos?.length ? ` (processos: ${existente.processos.join(", ")})` : ""}.
                  </p>
                  <label className="flex items-center gap-2 mb-1">
                    <input type="radio" checked={acrescentar} onChange={() => setAcrescentar(true)} />
                    Acrescentar o processo a ele
                  </label>
                  {acrescentar && (
                    <p className="text-xs text-foreground ml-6 mb-1">
                      As partes e o endereço deste formulário substituem os do substabelecimento existente.
                    </p>
                  )}
                  <label className="flex items-center gap-2">
                    <input type="radio" checked={!acrescentar} onChange={() => setAcrescentar(false)} />
                    Criar um novo
                  </label>
                </>
              ) : (
                <p className="text-foreground">
                  Este cliente já tem substabelecimento, mas {existente.motivo}. Será criado um novo.
                </p>
              )}
            </div>
          )}

          <div className="flex flex-wrap gap-3 mt-6">
            <a href={voltarPara} className={botaoSecundario}>Cancelar</a>
            {editando ? (
              <button type="button" className={botaoPrimario} onClick={salvarEdicao} disabled={ocupado}>
                {ocupado ? "Salvando..." : "Salvar nova versão"}
              </button>
            ) : (
              <button type="button" className={botaoPrimario} onClick={verPrevia} disabled={ocupado || bloqueado}>
                {ocupado ? "Gerando prévia..." : "Ver prévia"}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
