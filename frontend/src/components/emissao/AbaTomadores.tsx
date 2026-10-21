"use client";

import { useCallback, useEffect, useState } from "react";
import { emissaoApi, type Tomador, type TomadorIn } from "@/app/lib/emissao-api";
import { digitos, mensagemDeErro, semCamposDoServidor } from "@/app/lib/emissao";
import { Aviso, Campo, botaoPrimario, botaoSecundario, inputCls } from "./ui";

const VAZIO: TomadorIn = {
  documento: "", nome: "", emails: [], inscricao_municipal: null, optante_simples: false, orgao_publico: false,
  cep: null, logradouro: null, numero: null, complemento: null, bairro: null, municipio_ibge: null, uf: null,
};

export function AbaTomadores() {
  const [itens, setItens] = useState<Tomador[]>([]);
  const [busca, setBusca] = useState("");
  const [f, setF] = useState<TomadorIn>(VAZIO);
  const [emails, setEmails] = useState("");
  const [editando, setEditando] = useState<number | null>(null);
  const [aberto, setAberto] = useState(false);
  const [contrato, setContrato] = useState("");
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const carregar = useCallback(() => {
    emissaoApi.tomadores(busca).then(setItens).catch((e) => setAviso({ tipo: "erro", texto: mensagemDeErro(e) }));
  }, [busca]);
  useEffect(() => {
    const t = setTimeout(carregar, 250);
    return () => clearTimeout(t);
  }, [carregar]);

  const set = <K extends keyof TomadorIn>(k: K, v: TomadorIn[K]) => setF((x) => ({ ...x, [k]: v }));
  const abrir = (t?: Tomador) => {
    setEditando(t?.id ?? null);
    setF(t ? semCamposDoServidor(t) : VAZIO);
    setEmails((t?.emails ?? []).join(", "));
    setAberto(true);
    setAviso(null);
  };

  const doContrato = async () => {
    setOcupado(true);
    setAviso(null);
    try {
      const t = await emissaoApi.tomadorDeContrato(contrato.trim());
      abrir(t);
      setAviso({ tipo: "ok", texto: "Tomador do contrato carregado. O contrato guarda o endereço só como texto: complete o endereço abaixo." });
      carregar();
    } catch (err) {
      setAviso({ tipo: "erro", texto: mensagemDeErro(err) });
    } finally {
      setOcupado(false);
    }
  };

  const salvar = async (e: React.FormEvent) => {
    e.preventDefault();
    setOcupado(true);
    setAviso(null);
    const lista = emails.split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean);
    try {
      if (editando) {
        const { documento: _doc, ...resto } = f;
        void _doc;
        await emissaoApi.alterarTomador(editando, { ...resto, emails: lista, cep: f.cep ? digitos(f.cep) : null });
      } else {
        await emissaoApi.criarTomador({ ...f, emails: lista, cep: f.cep ? digitos(f.cep) : null });
      }
      setAberto(false);
      setAviso({ tipo: "ok", texto: "Tomador salvo." });
      carregar();
    } catch (err) {
      setAviso({ tipo: "erro", texto: mensagemDeErro(err) });
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="grow max-w-xs"><Campo rotulo="Buscar por nome ou documento"><input className={inputCls} value={busca} onChange={(e) => setBusca(e.target.value)} /></Campo></div>
        <div className="grow max-w-xs"><Campo rotulo="Criar a partir de um contrato"><input className={inputCls} value={contrato} onChange={(e) => setContrato(e.target.value)} placeholder="ID do contrato" /></Campo></div>
        <button onClick={doContrato} disabled={ocupado || !contrato.trim()} className={botaoSecundario}>Buscar no contrato</button>
        <button onClick={() => abrir()} className={`${botaoPrimario} ml-auto`}>Novo tomador</button>
      </div>
      {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}

      {aberto && (
        <form onSubmit={salvar} className="rounded-lg border border-border bg-card p-5 grid gap-4 sm:grid-cols-2" aria-label="Tomador">
          <Campo rotulo="CPF ou CNPJ"><input className={inputCls} value={f.documento} onChange={(e) => set("documento", e.target.value)} required disabled={!!editando} /></Campo>
          <Campo rotulo="Nome ou razão social"><input className={inputCls} value={f.nome} onChange={(e) => set("nome", e.target.value)} required /></Campo>
          <Campo rotulo="E-mails de cobrança" dica="Separe por vírgula."><input className={inputCls} value={emails} onChange={(e) => setEmails(e.target.value)} /></Campo>
          <Campo rotulo="Inscrição municipal"><input className={inputCls} value={f.inscricao_municipal ?? ""} onChange={(e) => set("inscricao_municipal", e.target.value || null)} /></Campo>
          <Campo rotulo="CEP"><input className={inputCls} value={f.cep ?? ""} onChange={(e) => set("cep", e.target.value || null)} inputMode="numeric" /></Campo>
          <Campo rotulo="Logradouro"><input className={inputCls} value={f.logradouro ?? ""} onChange={(e) => set("logradouro", e.target.value || null)} /></Campo>
          <Campo rotulo="Número"><input className={inputCls} value={f.numero ?? ""} onChange={(e) => set("numero", e.target.value || null)} /></Campo>
          <Campo rotulo="Complemento"><input className={inputCls} value={f.complemento ?? ""} onChange={(e) => set("complemento", e.target.value || null)} /></Campo>
          <Campo rotulo="Bairro"><input className={inputCls} value={f.bairro ?? ""} onChange={(e) => set("bairro", e.target.value || null)} /></Campo>
          <Campo rotulo="Código IBGE do município" dica="7 dígitos. BH: 3106200."><input className={inputCls} value={f.municipio_ibge ?? ""} onChange={(e) => set("municipio_ibge", digitos(e.target.value) || null)} maxLength={7} /></Campo>
          <Campo rotulo="UF"><input className={inputCls} value={f.uf ?? ""} onChange={(e) => set("uf", e.target.value.toUpperCase().slice(0, 2) || null)} maxLength={2} /></Campo>
          <div className="flex flex-col gap-2 justify-end">
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.optante_simples} onChange={(e) => set("optante_simples", e.target.checked)} /> Optante pelo Simples Nacional</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.orgao_publico} onChange={(e) => set("orgao_publico", e.target.checked)} /> Órgão público</label>
          </div>
          <p className="sm:col-span-2 text-xs text-muted">O endereço só entra na nota quando estiver completo (CEP, logradouro, número, bairro e código IBGE).</p>
          <div className="sm:col-span-2 flex gap-2">
            <button type="submit" disabled={ocupado} className={botaoPrimario}>{ocupado ? "Salvando…" : "Salvar tomador"}</button>
            <button type="button" onClick={() => setAberto(false)} className={botaoSecundario}>Cancelar</button>
          </div>
        </form>
      )}

      {itens.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted">Nenhum tomador. Crie um à mão ou a partir de um contrato.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted"><tr>
              <th scope="col" className="p-3">Nome</th><th scope="col" className="p-3">Documento</th><th scope="col" className="p-3">E-mails</th><th scope="col" className="p-3">Origem</th><th scope="col" className="p-3 text-right">Ações</th>
            </tr></thead>
            <tbody>
              {itens.map((t) => (
                <tr key={t.id} className="border-t border-border/40">
                  <td className="p-3">{t.nome}</td>
                  <td className="p-3 font-mono text-xs">{t.documento}</td>
                  <td className="p-3 text-xs">{t.emails.join(", ") || "—"}</td>
                  <td className="p-3 text-xs text-muted">{t.origem}</td>
                  <td className="p-3 text-right"><button onClick={() => abrir(t)} className="text-primary hover:underline">Editar</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
