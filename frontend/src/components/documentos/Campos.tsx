"use client";

import { useEffect, useState } from "react";
import { listColaboradores, type ColaboradorWizard } from "@/app/lib/api";
import { formatarCNPJ } from "@/app/lib/cnpj";
import {
  cnjValido,
  processoVazio,
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
  const setEmpresa = (i: number, parcial: Partial<AditivoForm["abrangencia"][number]>) =>
    set({ abrangencia: estado.abrangencia.map((e, k) => (k === i ? { ...e, ...parcial } : e)) });

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

      <h3 className="font-display text-sm font-semibold text-primary-dark mt-6 mb-2">Remuneração</h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-4">
        <FormField label="Valor mensal fixo" required error={erros["remuneracao.valor_mensal"]}>
          <CurrencyInput value={estado.valor_mensal} onChange={(v) => set({ valor_mensal: v })} error={!!erros["remuneracao.valor_mensal"]} />
        </FormField>
        <FormField label="Franquia (horas/mês)" hint="Opcional." error={erros["remuneracao.franquia_horas"]}>
          <Input type="number" min={1} step={1} inputMode="numeric" value={estado.franquia_horas} onChange={(e) => set({ franquia_horas: e.target.value })} error={!!erros["remuneracao.franquia_horas"]} />
        </FormField>
        <FormField label="Valor da hora excedente" hint="Opcional." error={erros["remuneracao.valor_hora_excedente"]}>
          <CurrencyInput value={estado.valor_hora_excedente} onChange={(v) => set({ valor_hora_excedente: v })} error={!!erros["remuneracao.valor_hora_excedente"]} />
        </FormField>
      </div>

      <Checkbox
        label="Admitir compensação de horas entre os meses (apuração a cada 12 meses)"
        checked={estado.compensacao_anual}
        onChange={(v) => set({ compensacao_anual: v })}
        hint="Inclui a cláusula Compensação e Faturamento."
      />

      <h3 className="font-display text-sm font-semibold text-primary-dark mt-6 mb-1">Abrangência</h3>
      <p className="text-xs text-muted mb-2">Outras empresas atendidas por este aditivo (grupo econômico). O contratante já entra automaticamente.</p>
      {estado.abrangencia.map((emp, i) => (
        <div key={i} className={cartao}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
            <FormField label="Razão social" required error={erros[`abrangencia.${i}.razao_social`]}>
              <Input value={emp.razao_social} onChange={(e) => setEmpresa(i, { razao_social: e.target.value })} error={!!erros[`abrangencia.${i}.razao_social`]} />
            </FormField>
            <FormField label="CNPJ" required error={erros[`abrangencia.${i}.cnpj`]}>
              <Input value={emp.cnpj} onChange={(e) => setEmpresa(i, { cnpj: formatarCNPJ(e.target.value) })} error={!!erros[`abrangencia.${i}.cnpj`]} inputMode="text" />
            </FormField>
          </div>
          <button type="button" className={botaoRemover} onClick={() => set({ abrangencia: estado.abrangencia.filter((_, k) => k !== i) })}>
            Remover empresa
          </button>
        </div>
      ))}
      <button type="button" className={botaoLink} onClick={() => set({ abrangencia: [...estado.abrangencia, { razao_social: "", cnpj: "" }] })}>
        + Adicionar empresa
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
