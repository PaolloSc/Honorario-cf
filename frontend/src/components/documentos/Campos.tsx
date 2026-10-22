"use client";

import { useEffect, useState } from "react";
import { listColaboradores, type ColaboradorWizard } from "@/app/lib/api";
import { formatarCNPJ } from "@/app/lib/cnpj";
import {
  alteracaoVazia,
  cnjValido,
  processoVazio,
  ROTULO_ALTERACAO,
  type Alteracao,
  type TipoAlteracao,
  substabelecidoVazio,
  type AditivoForm,
  type DistratoForm,
  type Erros,
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
        label="Ressalvar honorários de êxito"
        checked={estado.ressalva_exito}
        onChange={(v) => set({ ressalva_exito: v })}
        hint="Marcado (padrão), ressalva honorários e reembolsos vincendos, inclusive de êxito. Desmarcado, dá quitação total."
      />
      <Checkbox
        label="Substabelecer sem reserva de poderes e devolver documentos"
        checked={estado.substabelecer_e_devolver}
        onChange={(v) => set({ substabelecer_e_devolver: v })}
        hint="Inclui a cláusula 2.2 do modelo."
      />
    </>
  );
}

// ── Substabelecimento ─────────────────────────────────────────────────────

export function CamposSubstabelecimento({ estado, onChange, erros }: Props<SubstabelecimentoForm>) {
  const set = (parcial: Partial<SubstabelecimentoForm>) => onChange({ ...estado, ...parcial });
  const [colaboradores, setColaboradores] = useState<ColaboradorWizard[]>([]);
  const [escolhido, setEscolhido] = useState("");
  const [oab, setOab] = useState("");

  useEffect(() => {
    listColaboradores().then((r) => setColaboradores(r.colaboradores)).catch(() => setColaboradores([]));
  }, []);

  const adicionarSubstabelecente = () => {
    const c = colaboradores.find((x) => x.email === escolhido);
    if (!c || !oab.trim() || estado.substabelecentes.some((s) => s.email === c.email)) return;
    set({ substabelecentes: [...estado.substabelecentes, { nome: c.name, email: c.email, oab: oab.trim() }] });
    setEscolhido("");
    setOab("");
  };

  const setSubstabelecido = (i: number, parcial: Partial<SubstabelecimentoForm["substabelecidos"][number]>) =>
    set({ substabelecidos: estado.substabelecidos.map((s, k) => (k === i ? { ...s, ...parcial } : s)) });
  const setProcesso = (i: number, parcial: Partial<SubstabelecimentoForm["processos"][number]>) =>
    set({ processos: estado.processos.map((p, k) => (k === i ? { ...p, ...parcial } : p)) });

  return (
    <>
      <FormField label="Data do substabelecimento" required error={erros.data_documento}>
        <Input type="date" className="sm:max-w-xs" value={estado.data_documento} onChange={(e) => set({ data_documento: e.target.value })} error={!!erros.data_documento} />
      </FormField>

      <h3 className="font-display text-sm font-semibold text-primary-dark mt-6 mb-2">Outorgante (cliente)</h3>
      <div className="flex gap-4 mb-2 text-sm">
        <label className="flex items-center gap-2"><input type="radio" checked={estado.outorgante_pj} onChange={() => set({ outorgante_pj: true })} /> Empresa</label>
        <label className="flex items-center gap-2"><input type="radio" checked={!estado.outorgante_pj} onChange={() => set({ outorgante_pj: false })} /> Pessoa física</label>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
        <FormField label={estado.outorgante_pj ? "Razão social" : "Nome"} required error={erros.outorgante}>
          <Input value={estado.outorgante_nome} onChange={(e) => set({ outorgante_nome: e.target.value })} error={!!erros.outorgante} />
        </FormField>
        <FormField label={estado.outorgante_pj ? "CNPJ" : "CPF"} hint="Opcional.">
          <Input value={estado.outorgante_documento} onChange={(e) => set({ outorgante_documento: estado.outorgante_pj ? formatarCNPJ(e.target.value) : e.target.value })} />
        </FormField>
      </div>

      <h3 className="font-display text-sm font-semibold text-primary-dark mt-6 mb-1">Substabelecentes (C&amp;F)</h3>
      <p className="text-xs text-muted mb-2">Escolha no cadastro de colaboradores e informe a OAB como deve sair no texto (ex.: OAB/MG nº 36.959). Eles assinam o documento.</p>
      {estado.substabelecentes.map((s, i) => (
        <div key={s.email} className="flex flex-wrap items-center gap-2 text-sm mb-1">
          <span className="flex-1 min-w-48">{s.nome} — {s.oab}</span>
          <button type="button" className={botaoRemover} onClick={() => set({ substabelecentes: estado.substabelecentes.filter((_, k) => k !== i) })}>Remover</button>
        </div>
      ))}
      <div className="flex flex-col sm:flex-row gap-2 mt-2">
        <Select
          className="sm:flex-1"
          value={escolhido}
          onChange={(e) => setEscolhido(e.target.value)}
          placeholder="Colaborador…"
          options={colaboradores.filter((c) => c.email).map((c) => ({ value: c.email, label: c.name }))}
        />
        <Input className="sm:flex-1" value={oab} onChange={(e) => setOab(e.target.value)} placeholder="OAB/MG nº 00.000" />
        <button type="button" onClick={adicionarSubstabelecente} disabled={!escolhido || !oab.trim()} className="px-4 py-2 rounded-lg border border-primary text-primary text-sm font-medium disabled:opacity-40">
          Adicionar
        </button>
      </div>
      {erros.substabelecentes && <p className="text-xs text-danger mt-1">{erros.substabelecentes}</p>}

      <h3 className="font-display text-sm font-semibold text-primary-dark mt-6 mb-1">Substabelecidos (banca parceira)</h3>
      {erros.substabelecidos && <p className="text-xs text-danger mb-1">{erros.substabelecidos}</p>}
      {estado.substabelecidos.map((s, i) => (
        <div key={i} className={cartao}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
            <FormField label="Nome" required error={erros[`substabelecidos.${i}.nome`]}>
              <Input value={s.nome} onChange={(e) => setSubstabelecido(i, { nome: e.target.value })} error={!!erros[`substabelecidos.${i}.nome`]} />
            </FormField>
            <FormField label="Gênero" hint="Define Dr./Dra. e a concordância do texto.">
              <Select value={s.genero} onChange={(e) => setSubstabelecido(i, { genero: e.target.value as "F" | "M" })} options={[{ value: "F", label: "Feminino" }, { value: "M", label: "Masculino" }]} />
            </FormField>
            <FormField label="Estado civil" required error={erros[`substabelecidos.${i}.estado_civil`]}>
              <Input value={s.estado_civil} onChange={(e) => setSubstabelecido(i, { estado_civil: e.target.value })} error={!!erros[`substabelecidos.${i}.estado_civil`]} placeholder="casada" />
            </FormField>
            <FormField label="OAB" required error={erros[`substabelecidos.${i}.oab`]} hint="Como sai no texto: OAB/MG sob o nº 00.000">
              <Input value={s.oab} onChange={(e) => setSubstabelecido(i, { oab: e.target.value })} error={!!erros[`substabelecidos.${i}.oab`]} />
            </FormField>
          </div>
          {estado.substabelecidos.length > 1 && (
            <button type="button" className={botaoRemover} onClick={() => set({ substabelecidos: estado.substabelecidos.filter((_, k) => k !== i) })}>Remover substabelecido</button>
          )}
        </div>
      ))}
      <button type="button" className={botaoLink} onClick={() => set({ substabelecidos: [...estado.substabelecidos, substabelecidoVazio()] })}>+ Adicionar substabelecido</button>

      <FormField label="Endereço profissional dos substabelecidos" required error={erros.endereco_substabelecidos}>
        <Input value={estado.endereco_substabelecidos} onChange={(e) => set({ endereco_substabelecidos: e.target.value })} error={!!erros.endereco_substabelecidos} placeholder="Rua …, nº, bairro, cidade/UF, CEP" />
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
              <FormField label="Tipo">
                <Input value={p.tipo} onChange={(e) => setProcesso(i, { tipo: e.target.value })} placeholder="Processo" />
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
