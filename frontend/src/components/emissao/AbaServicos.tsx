"use client";

import { useCallback, useEffect, useState } from "react";
import { emissaoApi, type Servico, type ServicoIn } from "@/app/lib/emissao-api";
import { digitos, mensagemDeErro } from "@/app/lib/emissao";
import { Aviso, Campo, botaoPrimario, botaoSecundario, inputCls } from "./ui";

const VAZIO: ServicoIn = {
  nome: "", descricao_padrao: "Referente a serviços advocatícios", codigo_lc116: null, c_trib_nac: "", c_trib_mun: null,
  nbs: null, aliquota_iss: null, iss_retido_padrao: false, incluir_ibscbs: false, c_ind_op: null, cst_ibscbs: null,
  c_class_trib: null, ativo: true,
};

export function AbaServicos() {
  const [itens, setItens] = useState<Servico[]>([]);
  const [f, setF] = useState<ServicoIn>(VAZIO);
  const [editando, setEditando] = useState<number | null>(null);
  const [aberto, setAberto] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const carregar = useCallback(() => {
    emissaoApi.servicos(true).then(setItens).catch((e) => setAviso({ tipo: "erro", texto: mensagemDeErro(e) }));
  }, []);
  useEffect(carregar, [carregar]);

  const set = <K extends keyof ServicoIn>(k: K, v: ServicoIn[K]) => setF((x) => ({ ...x, [k]: v }));
  const abrir = (s?: Servico) => {
    setEditando(s?.id ?? null);
    setF(s ? { ...s } : VAZIO);
    setAberto(true);
    setAviso(null);
  };

  const salvar = async (e: React.FormEvent) => {
    e.preventDefault();
    setOcupado(true);
    setAviso(null);
    const corpo: ServicoIn = {
      ...f, nbs: f.nbs ? digitos(f.nbs) : null, aliquota_iss: f.aliquota_iss || null,
      c_trib_mun: f.c_trib_mun || null, c_ind_op: f.incluir_ibscbs ? f.c_ind_op : null,
      cst_ibscbs: f.incluir_ibscbs ? f.cst_ibscbs : null, c_class_trib: f.incluir_ibscbs ? f.c_class_trib : null,
    };
    try {
      if (editando) await emissaoApi.alterarServico(editando, corpo);
      else await emissaoApi.criarServico(corpo);
      setAberto(false);
      setAviso({ tipo: "ok", texto: "Serviço salvo." });
      carregar();
    } catch (err) {
      setAviso({ tipo: "erro", texto: mensagemDeErro(err) });
    } finally {
      setOcupado(false);
    }
  };

  const alternar = async (s: Servico) => {
    try {
      await emissaoApi.alterarServico(s.id, { ativo: !s.ativo });
      carregar();
    } catch (err) {
      setAviso({ tipo: "erro", texto: mensagemDeErro(err) });
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">Os códigos abaixo vão na DPS. Confirme com o contador antes de usar em produção.</p>
        <button onClick={() => abrir()} className={botaoPrimario}>Novo serviço</button>
      </div>
      {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}

      {aberto && (
        <form onSubmit={salvar} className="rounded-lg border border-border bg-card p-5 grid gap-4 sm:grid-cols-2" aria-label="Serviço">
          <Campo rotulo="Nome"><input className={inputCls} value={f.nome} onChange={(e) => set("nome", e.target.value)} required maxLength={100} /></Campo>
          <Campo rotulo="Item da LC 116" dica="Ex.: 17.14 (advocacia)."><input className={inputCls} value={f.codigo_lc116 ?? ""} onChange={(e) => set("codigo_lc116", e.target.value || null)} maxLength={10} /></Campo>
          <Campo rotulo="Código de tributação nacional" dica="6 dígitos. Ex.: 171401."><input className={inputCls} value={f.c_trib_nac} onChange={(e) => set("c_trib_nac", digitos(e.target.value))} required maxLength={6} inputMode="numeric" /></Campo>
          <Campo rotulo="Código de tributação municipal" dica="3 dígitos. BH parametriza o 17.14.01 como 001."><input className={inputCls} value={f.c_trib_mun ?? ""} onChange={(e) => set("c_trib_mun", digitos(e.target.value) || null)} maxLength={3} inputMode="numeric" /></Campo>
          <Campo rotulo="NBS" dica="9 dígitos; pode digitar com pontos."><input className={inputCls} value={f.nbs ?? ""} onChange={(e) => set("nbs", e.target.value || null)} /></Campo>
          <Campo rotulo="Alíquota do ISS (%)" dica="Só quando o regime exige (ISS retido por ME/EPP pelo Simples)."><input className={inputCls} value={f.aliquota_iss ?? ""} onChange={(e) => set("aliquota_iss", e.target.value.replace(",", ".") || null)} inputMode="decimal" /></Campo>
          <div className="sm:col-span-2"><Campo rotulo="Descrição padrão da nota"><textarea className={inputCls} rows={2} value={f.descricao_padrao} onChange={(e) => set("descricao_padrao", e.target.value)} required /></Campo></div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.iss_retido_padrao} onChange={(e) => set("iss_retido_padrao", e.target.checked)} /> ISS retido pelo tomador (padrão deste serviço)</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.incluir_ibscbs} onChange={(e) => set("incluir_ibscbs", e.target.checked)} /> Incluir IBS/CBS na nota</label>
          {f.incluir_ibscbs && (
            <>
              <Campo rotulo="Indicador da operação (cIndOp)" dica="6 dígitos. Ex.: 100301."><input className={inputCls} value={f.c_ind_op ?? ""} onChange={(e) => set("c_ind_op", digitos(e.target.value) || null)} maxLength={6} /></Campo>
              <Campo rotulo="CST" dica="3 dígitos. Ex.: 000."><input className={inputCls} value={f.cst_ibscbs ?? ""} onChange={(e) => set("cst_ibscbs", digitos(e.target.value) || null)} maxLength={3} /></Campo>
              <Campo rotulo="Classificação tributária" dica="6 dígitos. Ex.: 000001."><input className={inputCls} value={f.c_class_trib ?? ""} onChange={(e) => set("c_class_trib", digitos(e.target.value) || null)} maxLength={6} /></Campo>
            </>
          )}
          <div className="sm:col-span-2 flex gap-2">
            <button type="submit" disabled={ocupado} className={botaoPrimario}>{ocupado ? "Salvando…" : "Salvar serviço"}</button>
            <button type="button" onClick={() => setAberto(false)} className={botaoSecundario}>Cancelar</button>
          </div>
        </form>
      )}

      {itens.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted">Nenhum serviço cadastrado. Cadastre o primeiro para poder criar faturas.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted"><tr>
              <th scope="col" className="p-3">Nome</th><th scope="col" className="p-3">Cód. nacional / municipal</th>
              <th scope="col" className="p-3">NBS</th><th scope="col" className="p-3">ISS</th><th scope="col" className="p-3">IBS/CBS</th><th scope="col" className="p-3 text-right">Ações</th>
            </tr></thead>
            <tbody>
              {itens.map((s) => (
                <tr key={s.id} className={`border-t border-border/40 ${s.ativo ? "" : "text-muted"}`}>
                  <td className="p-3">{s.nome}{!s.ativo && <span className="ml-2 text-xs">(inativo)</span>}</td>
                  <td className="p-3 font-mono text-xs">{s.c_trib_nac}{s.c_trib_mun ? ` / ${s.c_trib_mun}` : ""}</td>
                  <td className="p-3 font-mono text-xs">{s.nbs ?? "—"}</td>
                  <td className="p-3">{s.aliquota_iss ? `${s.aliquota_iss}%` : "—"}{s.iss_retido_padrao ? " (retido)" : ""}</td>
                  <td className="p-3">{s.incluir_ibscbs ? "sim" : "não"}</td>
                  <td className="p-3 text-right space-x-2">
                    <button onClick={() => abrir(s)} className="text-primary hover:underline">Editar</button>
                    <button onClick={() => alternar(s)} className="text-muted hover:underline">{s.ativo ? "Desativar" : "Ativar"}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
