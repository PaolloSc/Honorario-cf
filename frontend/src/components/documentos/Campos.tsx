"use client";

import { useEffect, useState } from "react";
import { listColaboradores, lookupCNPJ, type ColaboradorWizard } from "@/app/lib/api";
import { cnpjValido, formatarCNPJ, limparCNPJ } from "@/app/lib/cnpj";
import {
  alteracaoVazia,
  cnjValido,
  formatarOabNumero,
  oabVazia,
  UFS,
  type Oab,
  processoVazio,
  ROTULO_ALTERACAO,
  type Alteracao,
  type TipoAlteracao,
  substabelecidoVazio,
  type AditivoForm,
  type DistratoForm,
  type Erros,
  type PoderesForm,
  type SubstabelecimentoForm,
} from "@/app/lib/documentos";
import CurrencyInput from "@/components/ui/CurrencyInput";
import FormField, { Checkbox, Input, Select, TextArea } from "@/components/ui/FormField";

interface Props<T> {
  estado: T;
  onChange: (novo: T) => void;
  erros: Erros;
}

const botaoLink = "text-xs font-medium text-primary hover:underline";
const botaoRemover = "text-xs font-medium text-danger hover:underline";
const cartao = "rounded-lg border border-border bg-background/60 p-3 mb-3";

// ── Aditivo ───────────────────────────────────────────────────────────────

export function CamposAditivo({ estado, onChange, erros }: Props<AditivoForm>) {
  const set = (parcial: Partial<AditivoForm>) => onChange({ ...estado, ...parcial });
  const setAlteracao = (i: number, parcial: Partial<Alteracao>) =>
    set({ alteracoes: estado.alteracoes.map((a, k) => (k === i ? { ...a, ...parcial } : a)) });

  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
        <FormField label="Data do aditivo" required error={erros.data_documento}>
          <Input type="date" value={estado.data_documento} onChange={(e) => set({ data_documento: e.target.value })} error={!!erros.data_documento} />
        </FormField>
        <FormField label="Data do contrato original" required error={erros.data_contrato_origem}>
          <Input type="date" value={estado.data_contrato_origem} onChange={(e) => set({ data_contrato_origem: e.target.value })} error={!!erros.data_contrato_origem} />
        </FormField>
      </div>

      <FormField label="Objeto do aditivo" required error={erros.objeto} hint='Completa a frase "tem por objeto a formalização de …".'>
        <TextArea value={estado.objeto} onChange={(e) => set({ objeto: e.target.value })} error={!!erros.objeto} placeholder="prestação de serviços de consultoria trabalhista" />
      </FormField>

      <h3 className="font-display text-sm font-semibold text-primary-dark mt-6 mb-1">Alterações no contrato original</h3>
      <p className="text-xs text-muted mb-2">Cada alteração vira um item numerado do aditivo.</p>
      {erros.alteracoes && <p className="text-xs text-danger mb-2">{erros.alteracoes}</p>}
      {estado.alteracoes.map((alt, i) => (
        <div key={i} className={cartao}>
          <FormField label="O que fazer" required>
            <Select
              value={alt.tipo}
              onChange={(e) => setAlteracao(i, { tipo: e.target.value as TipoAlteracao })}
              options={(Object.keys(ROTULO_ALTERACAO) as TipoAlteracao[]).map((t) => ({ value: t, label: ROTULO_ALTERACAO[t] }))}
            />
          </FormField>
          {alt.tipo !== "adicionar" && (
            <FormField label="Cláusula do contrato original" required error={erros[`alteracoes.${i}.clausula`]} hint='Ex.: "Cláusula 3ª, item 3.2".'>
              <Input value={alt.clausula} onChange={(e) => setAlteracao(i, { clausula: e.target.value })} error={!!erros[`alteracoes.${i}.clausula`]} />
            </FormField>
          )}
          {alt.tipo !== "excluir" && (
            <FormField label="Novo texto" required error={erros[`alteracoes.${i}.texto`]}>
              <TextArea value={alt.texto} onChange={(e) => setAlteracao(i, { texto: e.target.value })} error={!!erros[`alteracoes.${i}.texto`]} />
            </FormField>
          )}
          {estado.alteracoes.length > 1 && (
            <button type="button" className={botaoRemover} onClick={() => set({ alteracoes: estado.alteracoes.filter((_, k) => k !== i) })}>
              Remover alteração
            </button>
          )}
        </div>
      ))}
      <button type="button" className={botaoLink} onClick={() => set({ alteracoes: [...estado.alteracoes, alteracaoVazia()] })}>
        + Adicionar alteração
      </button>
    </>
  );
}

// ── Distrato ──────────────────────────────────────────────────────────────

export function CamposDistrato({ estado, onChange, erros }: Props<DistratoForm>) {
  const set = (parcial: Partial<DistratoForm>) => onChange({ ...estado, ...parcial });
  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
        <FormField label="Data do distrato" required error={erros.data_documento}>
          <Input type="date" value={estado.data_documento} onChange={(e) => set({ data_documento: e.target.value })} error={!!erros.data_documento} />
        </FormField>
        <FormField label="Data do contrato original" required error={erros.data_contrato_origem}>
          <Input type="date" value={estado.data_contrato_origem} onChange={(e) => set({ data_contrato_origem: e.target.value })} error={!!erros.data_contrato_origem} />
        </FormField>
      </div>
      <FormField label="Objeto do contrato original" required error={erros.objeto_contrato_origem} hint='Completa "tendo por objeto a prestação de serviços de …".'>
        <TextArea value={estado.objeto_contrato_origem} onChange={(e) => set({ objeto_contrato_origem: e.target.value })} error={!!erros.objeto_contrato_origem} placeholder="consultoria e contencioso de rotina" />
      </FormField>

      <h3 className="font-display text-sm font-semibold text-primary-dark mt-6 mb-1">Quitação</h3>
      <Checkbox
        label="Ressalvar honorários e reembolsos a vencer (inclusive êxito)"
        checked={estado.ressalva_exito}
        onChange={(v) => set({ ressalva_exito: v })}
        hint="Marcado (padrão), ressalva honorários e reembolsos vincendos, inclusive de êxito. Desmarcado, dá quitação total."
      />
      <Checkbox
        label="Substabelecer sem reserva de poderes e devolver documentos"
        checked={estado.substabelecer_e_devolver}
        onChange={(v) => set({ substabelecer_e_devolver: v })}
        hint="Marcado, o distrato também passa os processos aos novos advogados, sem reserva de poderes, e prevê a devolução dos documentos do cliente."
      />
      {estado.substabelecer_e_devolver && (
        <>
          <h3 className="font-display text-sm font-semibold text-primary-dark mt-6 mb-1">Substabelecimento gerado junto</h3>
          <p className="text-xs text-muted mb-2">O cliente e a data vêm do contrato e do distrato. Informe quem assina, quem recebe os poderes e os processos.</p>
          <CamposPoderes estado={estado} onChange={set} erros={erros} />
        </>
      )}
    </>
  );
}

// ── Substabelecimento ─────────────────────────────────────────────────────

/** Numero da OAB + UF (padrao MG, editavel). */
function CampoOab({ valor, onChange, erro }: { valor: Oab; onChange: (o: Oab) => void; erro?: string }) {
  return (
    <FormField label="OAB" required error={erro} hint="Só o número. A UF é MG, se não for outra.">
      <div className="flex gap-2">
        <div className="flex-1 min-w-0">
          <Input
            inputMode="text"
            value={valor.numero}
            onChange={(e) => onChange({ ...valor, numero: formatarOabNumero(e.target.value) })}
            error={!!erro}
            placeholder="00.000"
          />
        </div>
        <div className="w-24 shrink-0">
          <Select
            aria-label="UF da OAB"
            value={valor.uf}
            onChange={(e) => onChange({ ...valor, uf: e.target.value })}
            options={UFS.map((u) => ({ value: u, label: u }))}
          />
        </div>
      </div>
    </FormField>
  );
}

const formatarCEP = (d: string) => (d.length > 5 ? d.replace(/^(\d{5})(\d)/, "$1-$2") : d);

export function CamposPoderes({ estado, onChange, erros }: Props<PoderesForm> & { onChange: (parcial: Partial<PoderesForm>) => void }) {
  const set = (parcial: Partial<PoderesForm>) => onChange(parcial);
  const [colaboradores, setColaboradores] = useState<ColaboradorWizard[]>([]);
  const [escolhido, setEscolhido] = useState("");
  const [oab, setOab] = useState<Oab>(oabVazia());
  const [cep, setCep] = useState("");
  const [numeroEnd, setNumeroEnd] = useState("");
  const [msgCep, setMsgCep] = useState("");
  const [logradouro, setLogradouro] = useState("");

  useEffect(() => {
    listColaboradores().then((r) => setColaboradores(r.colaboradores)).catch(() => setColaboradores([]));
  }, []);

  const doCadastro = colaboradores.find((x) => x.email === escolhido);
  const oabsCadastradas = doCadastro?.oabs ?? [];
  const escolherColaborador = (email: string) => {
    setEscolhido(email);
    const o = colaboradores.find((x) => x.email === email)?.oabs ?? [];
    // Uma OAB cadastrada preenche sozinha; varias, a primeira, e o estado muda na lista; nenhuma: MG + digitar.
    setOab(o.length ? { numero: formatarOabNumero(o[0].numero), uf: o[0].uf } : oabVazia());
  };

  const adicionarSubstabelecente = () => {
    const c = colaboradores.find((x) => x.email === escolhido);
    if (!c || !oab.numero.trim() || estado.substabelecentes.some((s) => s.email === c.email)) return;
    set({ substabelecentes: [...estado.substabelecentes, { nome: c.name, email: c.email, oab }] });
    setEscolhido("");
    setOab(oabVazia());
  };

  const setSubstabelecente = (i: number, parcial: Partial<PoderesForm["substabelecentes"][number]>) =>
    set({ substabelecentes: estado.substabelecentes.map((s, k) => (k === i ? { ...s, ...parcial } : s)) });
  const setSubstabelecido = (i: number, parcial: Partial<PoderesForm["substabelecidos"][number]>) =>
    set({ substabelecidos: estado.substabelecidos.map((s, k) => (k === i ? { ...s, ...parcial } : s)) });
  const setProcesso = (i: number, parcial: Partial<PoderesForm["processos"][number]>) =>
    set({ processos: estado.processos.map((p, k) => (k === i ? { ...p, ...parcial } : p)) });

  // Endereco profissional (opcional): o CEP traz rua, bairro e cidade; numero e complemento entram a mao.
  const montarEndereco = (rua: string, num: string, cepFmt: string, resto: string) =>
    [rua, num && `nº ${num}`, resto].filter(Boolean).join(", ") + (cepFmt ? `, CEP ${cepFmt}` : "");
  const [bairroCidade, setBairroCidade] = useState("");
  const buscarCep = async (valor: string) => {
    const digitos = valor.replace(/\D/g, "").slice(0, 8);
    setCep(formatarCEP(digitos));
    setMsgCep("");
    if (digitos.length !== 8) return;
    try {
      const r = await (await fetch(`https://viacep.com.br/ws/${digitos}/json/`)).json();
      if (r.erro) {
        setMsgCep("CEP não encontrado. Digite o endereço no campo abaixo.");
        return;
      }
      const resto = [r.bairro, r.localidade && r.uf ? `${r.localidade}/${r.uf}` : ""].filter(Boolean).join(", ");
      setLogradouro(r.logradouro || "");
      setBairroCidade(resto);
      set({ endereco_substabelecidos: montarEndereco(r.logradouro || "", numeroEnd, formatarCEP(digitos), resto) });
    } catch {
      setMsgCep("Não foi possível buscar o CEP. Digite o endereço no campo abaixo.");
    }
  };
  const mudarNumeroEnd = (valor: string) => {
    setNumeroEnd(valor);
    if (logradouro || bairroCidade) set({ endereco_substabelecidos: montarEndereco(logradouro, valor, cep, bairroCidade) });
  };

  return (
    <>
      <h3 className="font-display text-sm font-semibold text-primary-dark mt-6 mb-1">Substabelecentes (C&amp;F)</h3>
      <p className="text-xs text-muted mb-2">Quem passa os poderes: advogados do escritório. Escolha no cadastro de colaboradores; a OAB vem do cadastro, se houver. Eles assinam o documento.</p>
      {estado.substabelecentes.map((s, i) => (
        <div key={s.email} className={cartao}>
          <p className="text-sm font-medium mb-1">{s.nome}</p>
          <CampoOab valor={s.oab} onChange={(o) => setSubstabelecente(i, { oab: o })} erro={erros[`substabelecentes.${i}.oab`]} />
          <button type="button" className={botaoRemover} onClick={() => set({ substabelecentes: estado.substabelecentes.filter((_, k) => k !== i) })}>Remover</button>
        </div>
      ))}
      <div className="flex flex-col sm:flex-row sm:items-start gap-2 mt-2">
        <Select
          className="sm:flex-1"
          value={escolhido}
          onChange={(e) => escolherColaborador(e.target.value)}
          placeholder="Colaborador…"
          options={colaboradores.filter((c) => c.email).map((c) => ({ value: c.email, label: c.name }))}
        />
        <div className="sm:flex-1">
          <CampoOab valor={oab} onChange={setOab} />
          {oabsCadastradas.length > 1 && (
            <div className="-mt-2 mb-2 flex flex-wrap gap-2 text-xs">
              {oabsCadastradas.map((o) => (
                <button
                  key={`${o.numero}-${o.uf}`}
                  type="button"
                  className={botaoLink}
                  onClick={() => setOab({ numero: formatarOabNumero(o.numero), uf: o.uf })}
                >
                  OAB/{o.uf} {formatarOabNumero(o.numero)}
                </button>
              ))}
            </div>
          )}
        </div>
        <button type="button" onClick={adicionarSubstabelecente} disabled={!escolhido || !oab.numero.trim()} className="px-4 py-2 rounded-lg border border-primary text-primary text-sm font-medium disabled:opacity-40">
          Adicionar
        </button>
      </div>
      {erros.substabelecentes && <p className="text-xs text-danger mt-1">{erros.substabelecentes}</p>}

      <h3 className="font-display text-sm font-semibold text-primary-dark mt-6 mb-1">Substabelecidos</h3>
      <p className="text-xs text-muted mb-2">Quem recebe os poderes: os advogados que passam a atuar nos processos.</p>
      {erros.substabelecidos && <p className="text-xs text-danger mb-1">{erros.substabelecidos}</p>}
      {estado.substabelecidos.map((s, i) => (
        <div key={i} className={cartao}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
            <FormField label="Nome" required error={erros[`substabelecidos.${i}.nome`]}>
              <Input value={s.nome} onChange={(e) => setSubstabelecido(i, { nome: e.target.value })} error={!!erros[`substabelecidos.${i}.nome`]} />
              {colaboradores.length > 0 && (
                <Select
                  className="mt-1"
                  aria-label="Preencher do cadastro de colaboradores"
                  value=""
                  onChange={(e) => {
                    const c = colaboradores.find((x) => x.name === e.target.value);
                    const o = c?.oabs?.[0];
                    if (c) setSubstabelecido(i, { nome: c.name, oab: o ? { numero: formatarOabNumero(o.numero), uf: o.uf } : s.oab });
                  }}
                  placeholder="Ou escolha do cadastro…"
                  options={colaboradores.map((c) => ({ value: c.name, label: c.name }))}
                />
              )}
            </FormField>
            <CampoOab valor={s.oab} onChange={(o) => setSubstabelecido(i, { oab: o })} erro={erros[`substabelecidos.${i}.oab`]} />
          </div>
          {estado.substabelecidos.length > 1 && (
            <button type="button" className={botaoRemover} onClick={() => set({ substabelecidos: estado.substabelecidos.filter((_, k) => k !== i) })}>Remover substabelecido</button>
          )}
        </div>
      ))}
      <button type="button" className={botaoLink} onClick={() => set({ substabelecidos: [...estado.substabelecidos, substabelecidoVazio()] })}>+ Adicionar substabelecido</button>

      <h4 className="text-sm font-medium text-foreground mt-5 mb-1">Endereço profissional dos substabelecidos <span className="text-muted font-normal">(opcional)</span></h4>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-4">
        <FormField label="CEP" error={msgCep || undefined}>
          <Input value={cep} onChange={(e) => buscarCep(e.target.value)} inputMode="numeric" placeholder="00000-000" />
        </FormField>
        <FormField label="Número">
          <Input value={numeroEnd} onChange={(e) => mudarNumeroEnd(e.target.value)} />
        </FormField>
      </div>
      <FormField label="Endereço" hint="Preenchido pelo CEP; pode ser digitado ou ajustado. Vazio, a frase do endereço sai do documento.">
        <Input value={estado.endereco_substabelecidos} onChange={(e) => set({ endereco_substabelecidos: e.target.value })} placeholder="Rua …, nº, bairro, cidade/UF, CEP" />
      </FormField>

      <h3 className="font-display text-sm font-semibold text-primary-dark mt-6 mb-1">Processos</h3>
      {erros.processos && <p className="text-xs text-danger mb-1">{erros.processos}</p>}
      {estado.processos.map((p, i) => {
        const aviso = p.numero.trim() && !cnjValido(p.numero) && !erros[`processos.${i}.numero`]
          ? "Padrão CNJ: 0000000-00.0000.0.00.0000 (confira o dígito verificador)"
          : undefined;
        return (
          <div key={i} className={cartao}>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-4">
              <FormField label="Tipo do feito" hint="Como o documento chama o caso.">
                <Input value={p.tipo} onChange={(e) => setProcesso(i, { tipo: e.target.value })} placeholder="Processo, Agravo de Instrumento…" />
              </FormField>
              <div className="sm:col-span-2">
                <FormField label="Número (CNJ)" required error={erros[`processos.${i}.numero`] ?? aviso}>
                  <Input value={p.numero} onChange={(e) => setProcesso(i, { numero: e.target.value })} error={!!(erros[`processos.${i}.numero`] ?? aviso)} placeholder="0000000-00.0000.0.00.0000" />
                </FormField>
              </div>
            </div>
            <FormField label="Partes / tribunal" hint="Opcional. Ex.: Cliente x Parte contrária">
              <Input value={p.descricao} onChange={(e) => setProcesso(i, { descricao: e.target.value })} />
            </FormField>
            {estado.processos.length > 1 && (
              <button type="button" className={botaoRemover} onClick={() => set({ processos: estado.processos.filter((_, k) => k !== i) })}>Remover processo</button>
            )}
          </div>
        );
      })}
      <button type="button" className={botaoLink} onClick={() => set({ processos: [...estado.processos, processoVazio()] })}>+ Adicionar processo</button>
    </>
  );
}

export function CamposSubstabelecimento({ estado, onChange, erros }: Props<SubstabelecimentoForm>) {
  const set = (parcial: Partial<SubstabelecimentoForm>) => onChange({ ...estado, ...parcial });
  const [msgCnpj, setMsgCnpj] = useState("");
  const [buscandoCnpj, setBuscandoCnpj] = useState(false);

  // CNPJ completo e valido: busca razao social como no cadastro de contratos; sem achar, digita-se a mao.
  const mudarDocumento = async (valor: string) => {
    const documento = estado.outorgante_pj ? formatarCNPJ(valor) : valor;
    set({ outorgante_documento: documento });
    setMsgCnpj("");
    if (!estado.outorgante_pj || limparCNPJ(documento).length !== 14 || !cnpjValido(documento)) return;
    setBuscandoCnpj(true);
    try {
      const d = await lookupCNPJ(documento);
      onChange({ ...estado, outorgante_documento: documento, outorgante_nome: d.razao_social });
    } catch {
      setMsgCnpj("CNPJ não encontrado na consulta. Preencha a razão social manualmente.");
    } finally {
      setBuscandoCnpj(false);
    }
  };

  return (
    <>
      <FormField label="Data do substabelecimento" required error={erros.data_documento}>
        <Input type="date" className="sm:max-w-xs" value={estado.data_documento} onChange={(e) => set({ data_documento: e.target.value })} error={!!erros.data_documento} />
      </FormField>

      <h3 className="font-display text-sm font-semibold text-primary-dark mt-6 mb-1">Outorgante (cliente)</h3>
      <p className="text-xs text-muted mb-2">O cliente que deu os poderes (procuração) que estão sendo substabelecidos.</p>
      <div className="flex gap-4 mb-2 text-sm">
        <label className="flex items-center gap-2"><input type="radio" checked={!estado.outorgante_pj} onChange={() => set({ outorgante_pj: false, outorgante_documento: "" })} /> Pessoa física</label>
        <label className="flex items-center gap-2"><input type="radio" checked={estado.outorgante_pj} onChange={() => set({ outorgante_pj: true, outorgante_documento: "" })} /> Pessoa jurídica</label>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
        <FormField
          label={estado.outorgante_pj ? "CNPJ" : "CPF"}
          hint={estado.outorgante_pj ? (buscandoCnpj ? "Buscando…" : "Com o CNPJ completo, a razão social é buscada.") : "Opcional."}
          error={msgCnpj || undefined}
        >
          <Input value={estado.outorgante_documento} onChange={(e) => mudarDocumento(e.target.value)} inputMode="numeric" />
        </FormField>
        <FormField label={estado.outorgante_pj ? "Razão social" : "Nome"} required error={erros.outorgante}>
          <Input value={estado.outorgante_nome} onChange={(e) => set({ outorgante_nome: e.target.value })} error={!!erros.outorgante} />
        </FormField>
      </div>

      <CamposPoderes estado={estado} onChange={set} erros={erros} />
    </>
  );
}
