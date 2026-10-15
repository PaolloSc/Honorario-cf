"use client";

import { useCallback, useEffect, useState } from "react";
import { emissaoApi, type EventoNota, type NotaEmitida } from "@/app/lib/emissao-api";
import { brl, mensagemDeErro } from "@/app/lib/emissao";
import { formatarDataHora } from "@/app/lib/datas";
import { Aviso, StatusBadge, botaoSecundario } from "./ui";

const ROTULO_EVENTO: Record<string, string> = {
  enviada: "DPS enviada", resposta: "Resposta do SEFIN", consulta: "Consulta pela DPS", erro: "Falha de comunicação",
};

function Linha({ e }: { e: EventoNota }) {
  const p = e.payload as { http?: number; chave?: string | null; erros?: { codigo: string; mensagem: string }[]; numero?: number; tipo?: string };
  return (
    <li className="text-xs">
      <span className="text-muted">{e.criado_em ? formatarDataHora(e.criado_em) : ""}</span>{" "}
      <strong>{ROTULO_EVENTO[e.tipo] ?? e.tipo}</strong>
      {p.http !== undefined && <> · HTTP {p.http}</>}
      {p.numero !== undefined && <> · DPS nº {p.numero}</>}
      {p.tipo && <> · {p.tipo}</>}
      {p.chave && <> · chave {p.chave}</>}
      {p.erros?.map((x, i) => <div key={i} className="text-danger">{x.codigo}: {x.mensagem}</div>)}
    </li>
  );
}

export function AbaNotas() {
  const [notas, setNotas] = useState<NotaEmitida[] | null>(null);
  const [aberta, setAberta] = useState<number | null>(null);
  const [eventos, setEventos] = useState<EventoNota[]>([]);
  const [msg, setMsg] = useState<{ tipo: "ok" | "erro" | "aviso"; texto: string } | null>(null);
  const [ocupado, setOcupado] = useState<number | null>(null);

  const carregar = useCallback(async () => {
    try {
      setNotas(await emissaoApi.notas());
    } catch (e) {
      setMsg({ tipo: "erro", texto: mensagemDeErro(e) });
    }
  }, []);
  useEffect(() => { carregar(); }, [carregar]);

  // enquanto houver nota processando, relê a lista (só lê; a consulta ao SEFIN é por botão)
  const processando = notas?.some((n) => n.status === "processando") ?? false;
  useEffect(() => {
    if (!processando) return;
    const t = setInterval(carregar, 15000);
    return () => clearInterval(t);
  }, [processando, carregar]);

  const detalhes = async (n: NotaEmitida) => {
    if (aberta === n.id) return setAberta(null);
    try {
      setEventos((await emissaoApi.nota(n.id)).eventos);
      setAberta(n.id);
    } catch (e) {
      setMsg({ tipo: "erro", texto: mensagemDeErro(e) });
    }
  };

  const consultar = async (n: NotaEmitida) => {
    setOcupado(n.id);
    setMsg(null);
    try {
      const nova = await emissaoApi.consultarNota(n.id);
      setMsg(nova.status === "processando"
        ? { tipo: "aviso", texto: "O SEFIN ainda não confirma esta nota. Tente de novo em alguns minutos." }
        : { tipo: nova.status === "autorizada" ? "ok" : "erro", texto: `Nota ${nova.status}.` });
      await carregar();
      if (aberta === n.id) setEventos((await emissaoApi.nota(n.id)).eventos);
    } catch (e) {
      setMsg({ tipo: "erro", texto: mensagemDeErro(e) });
    } finally {
      setOcupado(null);
    }
  };

  const baixar = async (n: NotaEmitida) => {
    try {
      await emissaoApi.baixarXml(n);
    } catch (e) {
      setMsg({ tipo: "erro", texto: mensagemDeErro(e) });
    }
  };

  if (!notas) return <p className="text-sm text-muted">Carregando…</p>;
  return (
    <div className="space-y-4" aria-live="polite">
      {msg && <Aviso tipo={msg.tipo}>{msg.texto}</Aviso>}
      <p className="text-xs text-muted">Notas de homologação (produção restrita): não têm valor fiscal. O XML é o documento da nota.</p>
      {notas.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted">Nenhuma nota emitida ainda. Emita a partir de uma fatura aprovada.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted"><tr>
              <th scope="col" className="p-3">NFS-e</th><th scope="col" className="p-3">DPS</th><th scope="col" className="p-3">Fatura</th>
              <th scope="col" className="p-3 text-right">Valor</th><th scope="col" className="p-3">Situação</th><th scope="col" className="p-3">Quando</th><th scope="col" className="p-3 text-right">Ações</th>
            </tr></thead>
            <tbody>
              {notas.map((n) => (
                <FragmentoNota key={n.id} n={n} aberta={aberta === n.id} eventos={eventos} ocupado={ocupado === n.id}
                  aoDetalhes={() => detalhes(n)} aoBaixar={() => baixar(n)} aoConsultar={() => consultar(n)} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function FragmentoNota({ n, aberta, eventos, ocupado, aoDetalhes, aoBaixar, aoConsultar }: {
  n: NotaEmitida; aberta: boolean; eventos: EventoNota[]; ocupado: boolean;
  aoDetalhes: () => void; aoBaixar: () => void; aoConsultar: () => void;
}) {
  return (
    <>
      <tr className="border-t border-border/40 align-top">
        <td className="p-3 font-mono text-xs">{n.numero_nfse ?? "—"}</td>
        <td className="p-3 text-xs">{n.dps_serie}/{n.dps_numero}</td>
        <td className="p-3 text-xs">#{n.fatura_id}</td>
        <td className="p-3 text-right tabular-nums">{brl(n.valor_servicos)}</td>
        <td className="p-3">
          <StatusBadge status={n.status} />
          {n.status === "rejeitada" && <div className="mt-1 max-w-xs text-xs text-danger">{n.erro_codigo}: {n.erro_mensagem}</div>}
        </td>
        <td className="p-3 text-xs">{n.emitida_em ?? n.criado_em ? formatarDataHora((n.emitida_em ?? n.criado_em) as string) : "—"}</td>
        <td className="p-3 text-right space-x-3 whitespace-nowrap">
          <button onClick={aoDetalhes} aria-expanded={aberta} className="text-primary hover:underline">{aberta ? "Ocultar" : "Detalhes"}</button>
          {n.tem_xml && <button onClick={aoBaixar} className="text-primary hover:underline">Baixar XML</button>}
          {n.status === "processando" && <button onClick={aoConsultar} disabled={ocupado} className={botaoSecundario}>{ocupado ? "Consultando…" : "Consultar"}</button>}
        </td>
      </tr>
      {aberta && (
        <tr className="bg-border/10"><td colSpan={7} className="p-3">
          {n.chave_acesso && <p className="mb-2 text-xs">Chave de acesso: <span className="font-mono">{n.chave_acesso}</span></p>}
          <ol className="space-y-1">{eventos.map((e) => <Linha key={e.id} e={e} />)}</ol>
        </td></tr>
      )}
    </>
  );
}
