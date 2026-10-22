"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import CurrencyInput from "@/components/ui/CurrencyInput";
import {
  emissaoApi, type Fatura, type FaturasResposta, type Servico, type Tomador, type Faturamento,
} from "@/app/lib/emissao-api";
import {
  ROTULO_STATUS, STATUS_FATURA, acoesDaFatura, brl, competenciaDoMes, ehErroDeRede, mensagemDeErro, resultadoDaEmissao,
  rotuloCompetencia,
} from "@/app/lib/emissao";
import { Aviso, Campo, ConfirmDialog, StatusBadge, botaoPrimario, botaoSecundario, inputCls } from "./ui";

type Msg = { tipo: "ok" | "erro" | "aviso"; texto: string };

export function AbaFaturas() {
  const [dados, setDados] = useState<FaturasResposta | null>(null);
  const [filtro, setFiltro] = useState<string>("");
  const [tomadores, setTomadores] = useState<Tomador[]>([]);
  const [servicos, setServicos] = useState<Servico[]>([]);
  const [msg, setMsg] = useState<Msg | null>(null);
  const [emitindo, setEmitindo] = useState<{ fatura: Fatura; chave: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erroEmitir, setErroEmitir] = useState("");

  const carregar = useCallback(async () => {
    try {
      const [f, t, s] = await Promise.all([emissaoApi.faturas(filtro || undefined), emissaoApi.tomadores(""), emissaoApi.servicos(true)]);
      setDados(f);
      setTomadores(t);
      setServicos(s);
    } catch (e) {
      setMsg({ tipo: "erro", texto: mensagemDeErro(e) });
    }
  }, [filtro]);
  useEffect(() => { carregar(); }, [carregar]);

  const nomeTomador = useMemo(() => new Map(tomadores.map((t) => [t.id, t.nome])), [tomadores]);
  const nomeServico = useMemo(() => new Map(servicos.map((s) => [s.id, s.nome])), [servicos]);

  const agir = async (acao: () => Promise<unknown>, ok: string) => {
    setMsg(null);
    try {
      await acao();
      setMsg({ tipo: "ok", texto: ok });
      await carregar();
    } catch (e) {
      setMsg({ tipo: "erro", texto: mensagemDeErro(e) });
    }
  };

  const emitir = async () => {
    if (!emitindo) return;
    setOcupado(true);
    setErroEmitir("");
    try {
      // a mesma chave enquanto o diálogo estiver aberto: repetir depois de um erro de rede é seguro
      const nota = await emissaoApi.emitir(emitindo.fatura.id, emitindo.chave);
      setEmitindo(null);
      setMsg(resultadoDaEmissao(nota));
      await carregar();
    } catch (e) {
      if (ehErroDeRede(e)) {
        // sem resposta: o diálogo fica aberto com a MESMA chave; repetir é seguro
        setErroEmitir(`${mensagemDeErro(e)} Sem resposta do servidor: pode tentar de novo, a mesma tentativa não gera nota em duplicidade.`);
      } else {
        // a API respondeu com erro (regra de negócio): outra tentativa será outra intenção
        setEmitindo(null);
        setMsg({ tipo: "erro", texto: mensagemDeErro(e) });
      }
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="space-y-6">
      {msg && <Aviso tipo={msg.tipo}>{msg.texto}</Aviso>}

      <div role="group" aria-label="Totais por situação" className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {STATUS_FATURA.map((s) => {
          const t = dados?.totais[s];
          return (
            <button key={s} onClick={() => setFiltro(filtro === s ? "" : s)} aria-pressed={filtro === s}
              className={`rounded-lg border p-3 text-left ${filtro === s ? "border-primary-dark bg-primary/[0.08]" : "border-border bg-card"}`}>
              <span className="block text-xs text-muted">{ROTULO_STATUS[s]}</span>
              <span className="block text-base font-semibold tabular-nums">{brl(t?.valor ?? 0)}</span>
              <span className="block text-xs text-muted">{t?.quantidade ?? 0} fatura(s)</span>
            </button>
          );
        })}
      </div>

      <NovaFatura tomadores={tomadores} servicos={servicos} aoCriar={() => { setMsg({ tipo: "ok", texto: "Fatura criada em rascunho." }); carregar(); }} aoErro={(t) => setMsg({ tipo: "erro", texto: t })} />
      <ContratoPanel tomadores={tomadores} servicos={servicos} aoMsg={setMsg} />

      {!dados ? (
        <p className="text-sm text-muted">Carregando…</p>
      ) : dados.itens.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted">
          {filtro ? "Nenhuma fatura nesta situação." : "Nenhuma fatura. Crie a primeira acima."}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted"><tr>
              <th scope="col" className="p-3">Competência</th><th scope="col" className="p-3">Contrato</th><th scope="col" className="p-3">Tomador</th>
              <th scope="col" className="p-3">Serviço</th><th scope="col" className="p-3 text-right">Valor</th><th scope="col" className="p-3">Situação</th><th scope="col" className="p-3 text-right">Ações</th>
            </tr></thead>
            <tbody>
              {dados.itens.map((f) => {
                const a = acoesDaFatura(f.status);
                return (
                  <tr key={f.id} className="border-t border-border/40">
                    <td className="p-3">{rotuloCompetencia(f.competencia)}</td>
                    <td className="p-3 font-mono text-xs">{f.contract_id.slice(0, 8)}</td>
                    <td className="p-3">{nomeTomador.get(f.tomador_id) ?? `#${f.tomador_id}`}</td>
                    <td className="p-3">{nomeServico.get(f.servico_id) ?? `#${f.servico_id}`}</td>
                    <td className="p-3 text-right tabular-nums">{brl(f.valor_bruto)}</td>
                    <td className="p-3"><StatusBadge status={f.status} /></td>
                    <td className="p-3 text-right space-x-3 whitespace-nowrap">
                      {a.aprovar && <button onClick={() => agir(() => emissaoApi.aprovarFatura(f.id), "Fatura aprovada.")} className="text-primary hover:underline">Aprovar</button>}
                      {a.emitir && <button onClick={() => { setErroEmitir(""); setEmitindo({ fatura: f, chave: crypto.randomUUID() }); }} className="font-medium text-primary-dark hover:underline">Emitir nota</button>}
                      {a.excluir && <button onClick={() => agir(() => emissaoApi.excluirFatura(f.id), "Fatura excluída.")} className="text-danger hover:underline">Excluir</button>}
                      {f.status === "emitindo" && <span className="text-xs text-muted">acompanhe em Notas emitidas</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {emitindo && (
        <ConfirmDialog
          titulo="Emitir NFS-e?"
          verbo="Emitir nota"
          ocupado={ocupado}
          erro={erroEmitir}
          onConfirmar={emitir}
          onCancelar={() => setEmitindo(null)}
          texto={<>
            Será enviada ao SEFIN (<strong>produção restrita</strong>, sem valor fiscal) a nota de{" "}
            <strong>{brl(emitindo.fatura.valor_bruto)}</strong> para{" "}
            <strong>{nomeTomador.get(emitindo.fatura.tomador_id) ?? "o tomador"}</strong>, competência{" "}
            {rotuloCompetencia(emitindo.fatura.competencia)}. Emitir é um ato fiscal: uma nota errada exige cancelamento.
          </>}
        />
      )}
    </div>
  );
}

function NovaFatura({ tomadores, servicos, aoCriar, aoErro }: {
  tomadores: Tomador[]; servicos: Servico[]; aoCriar: () => void; aoErro: (t: string) => void;
}) {
  const [contrato, setContrato] = useState("");
  const [tomador, setTomador] = useState("");
  const [servico, setServico] = useState("");
  const [mes, setMes] = useState("");
  const [valor, setValor] = useState<number | undefined>();
  const [descricao, setDescricao] = useState("");
  const [venc, setVenc] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valor) return aoErro("Informe o valor da fatura.");
    setOcupado(true);
    try {
      await emissaoApi.criarFatura({
        contract_id: contrato.trim(), tomador_id: Number(tomador), servico_id: Number(servico),
        competencia: competenciaDoMes(mes), valor_bruto: valor.toFixed(2),
        descricao: descricao.trim() || undefined, vencimento: venc || null,
      });
      setValor(undefined);
      setDescricao("");
      aoCriar();
    } catch (err) {
      aoErro(mensagemDeErro(err));
    } finally {
      setOcupado(false);
    }
  };

  return (
    <details className="rounded-lg border border-border bg-card p-4">
      <summary className="cursor-pointer text-sm font-semibold text-primary-dark">Nova fatura</summary>
      <form onSubmit={enviar} className="mt-4 grid gap-4 sm:grid-cols-3">
        <Campo rotulo="ID do contrato"><input className={inputCls} value={contrato} onChange={(e) => setContrato(e.target.value)} required /></Campo>
        <Campo rotulo="Tomador">
          <select className={inputCls} value={tomador} onChange={(e) => setTomador(e.target.value)} required>
            <option value="">Selecione…</option>
            {tomadores.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
          </select>
        </Campo>
        <Campo rotulo="Serviço">
          <select className={inputCls} value={servico} onChange={(e) => setServico(e.target.value)} required>
            <option value="">Selecione…</option>
            {servicos.filter((s) => s.ativo).map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
          </select>
        </Campo>
        <Campo rotulo="Competência"><input type="month" className={inputCls} value={mes} onChange={(e) => setMes(e.target.value)} required /></Campo>
        <Campo rotulo="Valor"><CurrencyInput value={valor} onChange={setValor} /></Campo>
        <Campo rotulo="Vencimento (opcional)"><input type="date" className={inputCls} value={venc} onChange={(e) => setVenc(e.target.value)} /></Campo>
        <div className="sm:col-span-3"><Campo rotulo="Descrição na nota (opcional)" dica="Vazio usa a descrição padrão do serviço."><input className={inputCls} value={descricao} onChange={(e) => setDescricao(e.target.value)} /></Campo></div>
        <div className="sm:col-span-3"><button type="submit" disabled={ocupado} className={botaoPrimario}>{ocupado ? "Criando…" : "Criar fatura"}</button></div>
      </form>
    </details>
  );
}

/** Quem fatura o contrato. Padrão: Legal One. Só contrato do Honorário emite nota. */
function ContratoPanel({ tomadores, servicos, aoMsg }: { tomadores: Tomador[]; servicos: Servico[]; aoMsg: (m: Msg) => void }) {
  const [contrato, setContrato] = useState("");
  const [cfg, setCfg] = useState<Faturamento | null>(null);

  const buscar = async () => {
    try {
      setCfg(await emissaoApi.faturamento(contrato.trim()));
    } catch (e) {
      setCfg(null);
      aoMsg({ tipo: "erro", texto: mensagemDeErro(e) });
    }
  };
  const salvar = async () => {
    if (!cfg) return;
    try {
      const { contract_id: _id, ...corpo } = cfg;
      void _id;
      setCfg(await emissaoApi.definirFaturamento(cfg.contract_id, corpo));
      aoMsg({ tipo: "ok", texto: "Faturamento do contrato salvo." });
    } catch (e) {
      aoMsg({ tipo: "erro", texto: mensagemDeErro(e) });
    }
  };

  return (
    <details className="rounded-lg border border-border bg-card p-4">
      <summary className="cursor-pointer text-sm font-semibold text-primary-dark">Quem fatura um contrato</summary>
      <p className="mt-2 text-xs text-muted">Todo contrato começa com a nota emitida pelo Legal One. Só mude para este sistema quando combinado com o financeiro, para não emitir a nota duas vezes.</p>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <Campo rotulo="ID do contrato"><input className={inputCls} value={contrato} onChange={(e) => setContrato(e.target.value)} /></Campo>
        <button onClick={buscar} disabled={!contrato.trim()} className={botaoSecundario}>Consultar</button>
      </div>
      {cfg && (
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <Campo rotulo="Quem emite a nota deste contrato">
            <select className={inputCls} value={cfg.origem} onChange={(e) => setCfg({ ...cfg, origem: e.target.value as Faturamento["origem"] })}>
              <option value="legalone">Legal One (padrão)</option>
              <option value="honorario">Este sistema (Honorário-CF emite a NFS-e)</option>
            </select>
          </Campo>
          <Campo rotulo="Tomador padrão" dica="Quem paga a nota; vem preenchido nas novas faturas.">
            <select className={inputCls} value={cfg.tomador_id ?? ""} onChange={(e) => setCfg({ ...cfg, tomador_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">—</option>
              {tomadores.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
            </select>
          </Campo>
          <Campo rotulo="Serviço padrão">
            <select className={inputCls} value={cfg.servico_id ?? ""} onChange={(e) => setCfg({ ...cfg, servico_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">—</option>
              {servicos.filter((s) => s.ativo).map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
            </select>
          </Campo>
          <div className="sm:col-span-3"><button onClick={salvar} className={botaoPrimario}>Salvar faturamento do contrato</button></div>
        </div>
      )}
    </details>
  );
}
