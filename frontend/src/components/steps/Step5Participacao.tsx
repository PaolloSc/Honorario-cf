"use client";

import { useEffect, useState } from "react";
import FormField, { Checkbox, Input, Select, Toggle } from "@/components/ui/FormField";
import CurrencyInput from "@/components/ui/CurrencyInput";
import type { EscopoItem, Participacao, ParticipacaoValorTipo, TipoHonorario } from "@/types/contract";
import { ESCOPO_LABELS, HONORARIO_LABELS } from "@/types/contract";
import { listColaboradores } from "@/app/lib/api";

function buildObjetoLines(escopos: EscopoItem[]): string[] {
  const lines: string[] = [];
  escopos.forEach((escopo) => {
    const label = ESCOPO_LABELS[escopo.tipo] || escopo.tipo;
    let detail = label;
    if (escopo.descricao_custom) detail += ` - ${escopo.descricao_custom}`;
    if (escopo.numero_autos) detail += ` | Autos: ${escopo.numero_autos}`;
    if (escopo.demandas) detail += ` | Demandas: ${escopo.demandas}`;
    if (escopo.pessoas_patrimonios) detail += ` | Pessoas/Patrimônios: ${escopo.pessoas_patrimonios}`;
    if (escopo.tipo_reestruturacao) detail += ` | Reestruturação: ${escopo.tipo_reestruturacao}`;
    if (escopo.documentos) detail += ` | Documentos: ${escopo.documentos}`;
    if (escopo.consulta) detail += ` | Consulta: ${escopo.consulta}`;
    if (escopo.subtipo_memoriais) {
      const a: string[] = [];
      if (escopo.subtipo_memoriais.elaboracao_memoriais) a.push("Elaboração de memoriais");
      if (escopo.subtipo_memoriais.despacho_memoriais) a.push("Despacho de memoriais");
      if (escopo.subtipo_memoriais.sustentacao_oral_relator) a.push("Sustentação oral (relator)");
      if (escopo.subtipo_memoriais.sustentacao_oral_todos_julgadores) a.push("Sustentação oral (todos julgadores)");
      if (a.length > 0) detail += ` | Atividades: ${a.join(", ")}`;
    }
    lines.push(detail);
  });
  return lines;
}

function maskTelefoneBR(value: string): string {
  const d = value.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d.length ? `(${d}` : "";
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
}

const VALOR_TIPOS: Array<{ value: ParticipacaoValorTipo; label: string }> = [
  { value: "percentual", label: "Percentual (%)" },
  { value: "valor", label: "Valor (R$)" },
  { value: "outro", label: "Outro critério" },
];

interface Step5Props {
  participacao: Participacao;
  onChange: (participacao: Participacao) => void;
  escopos: EscopoItem[];
}

export default function Step5Participacao({ participacao, onChange, escopos }: Step5Props) {
  const objetoLines = buildObjetoLines(escopos);
  const [colaboradores, setColaboradores] = useState<Array<{ name: string; email: string; role: string }>>([]);
  const [colabError, setColabError] = useState("");
  const [loadingColab, setLoadingColab] = useState(true);

  useEffect(() => {
    let active = true;
    listColaboradores()
      .then((res) => { if (active) setColaboradores(res.colaboradores); })
      .catch(() => { if (active) setColabError("Não foi possível carregar a lista de advogados."); })
      .finally(() => { if (active) setLoadingColab(false); });
    return () => { active = false; };
  }, []);

  const set = (partial: Partial<Participacao>) => onChange({ ...participacao, ...partial });

  const escopoLabel = (e: EscopoItem) =>
    (ESCOPO_LABELS[e.tipo] || e.tipo) + (e.descricao_custom ? ` - ${e.descricao_custom}` : "");

  const setBaseTipo = (tipo: "escopo" | "honorario") =>
    set({ base_tipo: tipo, base_escopo_index: undefined, base_honorario: undefined, base_label: "" });

  const selecionarEscopo = (idx: number) =>
    set({ base_escopo_index: idx, base_honorario: undefined, base_label: escopoLabel(escopos[idx]) });

  const selecionarHonorario = (idx: number, hon: TipoHonorario) =>
    set({
      base_escopo_index: idx,
      base_honorario: hon,
      base_label: `${escopoLabel(escopos[idx])} · ${HONORARIO_LABELS[hon]}`,
    });

  const paresHonorario: Array<{ idx: number; hon: TipoHonorario; label: string }> = [];
  escopos.forEach((e, idx) => {
    (e.honorarios ?? []).forEach((hon) => {
      paresHonorario.push({ idx, hon, label: `${escopoLabel(e)} — ${HONORARIO_LABELS[hon]}` });
    });
  });

  const baseSelecionada = Boolean(participacao.base_label);

  const setValorTipo = (tipo: ParticipacaoValorTipo) =>
    set({ valor_tipo: tipo, valor_percentual: "", valor_monetario: undefined, valor_outro: "" });

  const toggleParaQuem = (nome: string, checked: boolean) => {
    const atual = participacao.para_quem ?? [];
    set({ para_quem: checked ? [...atual, nome] : atual.filter((n) => n !== nome) });
  };

  const baseNomeOptions = colaboradores.map((c) => ({ value: c.name, label: c.name }));
  const optionsComSalvo = (saved?: string) =>
    saved && !baseNomeOptions.some((o) => o.value === saved)
      ? [...baseNomeOptions, { value: saved, label: saved }]
      : baseNomeOptions;

  const nomesColab = colaboradores.map((c) => c.name);
  const paraQuemSel = participacao.para_quem ?? [];
  const nomesParaExibir = Array.from(new Set([...nomesColab, ...paraQuemSel]));

  return (
    <div>
      <h2 className="text-xl font-bold text-primary mb-2">5. Participações (Ficha Interna)</h2>
      <p className="text-sm text-muted mb-2">
        Informações internas sobre participação. O cliente <strong>não terá acesso</strong> a estes dados.
      </p>
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-6">
        <p className="text-xs text-yellow-800 font-medium">
          Atenção: Esta ficha é apenas para fins internos do escritório.
        </p>
      </div>

      {objetoLines.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <p className="text-sm font-semibold text-blue-900 mb-2">Objeto do Contrato</p>
          <ul className="list-disc list-inside space-y-1">
            {objetoLines.map((line, idx) => (
              <li key={idx} className="text-sm text-blue-800">{line}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
        <Toggle
          label="Este contrato terá participação?"
          value={participacao.tem_participacao}
          onChange={(v) => set({ tem_participacao: v })}
        />

        {participacao.tem_participacao && (
          <div className="space-y-6 mt-4">
            {/* Base da participação */}
            <div>
              <p className="text-sm font-semibold text-foreground mb-2">Base da participação</p>
              {escopos.length === 0 ? (
                <p className="text-xs text-muted">Defina escopos na etapa 2 primeiro.</p>
              ) : (
                <>
                  <div className="flex flex-wrap gap-4 mb-3">
                    {(["escopo", "honorario"] as const).map((t) => (
                      <label key={t} className="flex items-center gap-2 cursor-pointer text-sm">
                        <input
                          type="radio"
                          name="base_tipo"
                          checked={participacao.base_tipo === t}
                          onChange={() => setBaseTipo(t)}
                          className="h-4 w-4 text-primary focus:ring-primary-light"
                        />
                        {t === "escopo" ? "Escopo" : "Honorário"}
                      </label>
                    ))}
                  </div>

                  {participacao.base_tipo === "escopo" && (
                    <div className="space-y-2">
                      {escopos.map((e, idx) => (
                        <label key={idx} className="flex items-start gap-2 cursor-pointer text-sm">
                          <input
                            type="radio"
                            name="base_escopo"
                            checked={participacao.base_escopo_index === idx && !participacao.base_honorario}
                            onChange={() => selecionarEscopo(idx)}
                            className="h-4 w-4 mt-0.5 text-primary focus:ring-primary-light"
                          />
                          {escopoLabel(e)}
                        </label>
                      ))}
                    </div>
                  )}

                  {participacao.base_tipo === "honorario" && (
                    <div className="space-y-2">
                      {paresHonorario.length === 0 && (
                        <p className="text-xs text-muted">Nenhum honorário definido nos escopos.</p>
                      )}
                      {paresHonorario.map((p) => (
                        <label key={`${p.idx}-${p.hon}`} className="flex items-start gap-2 cursor-pointer text-sm">
                          <input
                            type="radio"
                            name="base_honorario"
                            checked={participacao.base_escopo_index === p.idx && participacao.base_honorario === p.hon}
                            onChange={() => selecionarHonorario(p.idx, p.hon)}
                            className="h-4 w-4 mt-0.5 text-primary focus:ring-primary-light"
                          />
                          {p.label}
                        </label>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>

            {baseSelecionada && (
              <>
            {/* Valor da participação */}
            <div>
              <p className="text-sm font-semibold text-foreground mb-2">Valor da participação</p>
              <div className="flex flex-wrap gap-4 mb-3">
                {VALOR_TIPOS.map((t) => (
                  <label key={t.value} className="flex items-center gap-2 cursor-pointer text-sm">
                    <input
                      type="radio"
                      name="valor_tipo"
                      checked={participacao.valor_tipo === t.value}
                      onChange={() => setValorTipo(t.value)}
                      className="h-4 w-4 text-primary focus:ring-primary-light"
                    />
                    {t.label}
                  </label>
                ))}
              </div>

              {participacao.valor_tipo === "percentual" && (
                <FormField label="Percentual (%)">
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    value={participacao.valor_percentual ?? ""}
                    onChange={(e) => set({ valor_percentual: e.target.value })}
                    placeholder="Ex: 10"
                  />
                </FormField>
              )}

              {participacao.valor_tipo === "valor" && (
                <FormField label="Valor (R$)">
                  <CurrencyInput
                    value={participacao.valor_monetario}
                    onChange={(v) => set({ valor_monetario: v })}
                    placeholder="0,00"
                  />
                </FormField>
              )}

              {participacao.valor_tipo === "outro" && (
                <FormField label="Outro critério">
                  <Input
                    value={participacao.valor_outro ?? ""}
                    onChange={(e) => set({ valor_outro: e.target.value })}
                    placeholder="Descreva o critério da participação"
                  />
                </FormField>
              )}
            </div>

            {/* Para quem (multi advogados) */}
            <div>
              <p className="text-sm font-semibold text-foreground mb-2">Para quem?</p>
              {colabError && <p className="text-xs text-red-500 mb-2">{colabError}</p>}
              {loadingColab && <p className="text-xs text-muted">Carregando advogados...</p>}
              {!loadingColab && nomesParaExibir.length === 0 && (
                <p className="text-xs text-muted">Nenhum colaborador encontrado.</p>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {nomesParaExibir.map((nome) => (
                  <Checkbox
                    key={nome}
                    label={nome}
                    checked={paraQuemSel.includes(nome)}
                    onChange={(checked) => toggleParaQuem(nome, checked)}
                  />
                ))}
              </div>
            </div>

            {/* Natureza + responsáveis */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField label="Natureza da participação">
                <Select
                  value={participacao.natureza || ""}
                  onChange={(e) => set({ natureza: e.target.value })}
                  placeholder="Selecione a natureza da participação"
                  options={[
                    { value: "Captação", label: "Captação" },
                    { value: "Performance", label: "Performance" },
                    { value: "Captação e performance", label: "Captação e performance" },
                    { value: "Projeto", label: "Projeto" },
                    { value: "Outro", label: "Outro" },
                  ]}
                />
              </FormField>

              <FormField label="Responsável pela captação">
                <Select
                  value={participacao.responsavel_captacao || ""}
                  onChange={(e) => set({ responsavel_captacao: e.target.value })}
                  placeholder="Selecione o advogado"
                  options={optionsComSalvo(participacao.responsavel_captacao)}
                />
              </FormField>

              <FormField label="Responsável pela gestão do contrato">
                <Select
                  value={participacao.responsavel_gestao || ""}
                  onChange={(e) => set({ responsavel_gestao: e.target.value })}
                  placeholder="Selecione o advogado"
                  options={optionsComSalvo(participacao.responsavel_gestao)}
                />
              </FormField>
            </div>

            {/* Contato financeiro do cliente (3 campos) */}
            <div>
              <p className="text-sm font-semibold text-foreground mb-2">
                Contato do responsável financeiro do cliente
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <FormField label="Nome">
                  <Input
                    value={participacao.contato_financeiro_nome ?? ""}
                    onChange={(e) => set({ contato_financeiro_nome: e.target.value })}
                    placeholder="Nome"
                  />
                </FormField>
                <FormField label="E-mail">
                  <Input
                    type="email"
                    value={participacao.contato_financeiro_email ?? ""}
                    onChange={(e) => set({ contato_financeiro_email: e.target.value })}
                    placeholder="email@exemplo.com"
                  />
                </FormField>
                <FormField label="Telefone">
                  <Input
                    value={participacao.contato_financeiro_telefone ?? ""}
                    onChange={(e) => set({ contato_financeiro_telefone: maskTelefoneBR(e.target.value) })}
                    placeholder="(00) 00000-0000"
                  />
                </FormField>
              </div>
            </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
