"use client";

import { useCallback, useEffect, useState } from "react";
import { emissaoApi, type EmissorIn, type EmissorOut } from "@/app/lib/emissao-api";
import {
  OPCOES_OP_SIMP_NAC, OPCOES_REG_AP_TRIB_SN, OPCOES_REG_ESP_TRIB, digitos, mensagemDeErro,
} from "@/app/lib/emissao";
import { formatarData } from "@/app/lib/datas";
import { Aviso, Campo, botaoPrimario, botaoSecundario, inputCls } from "./ui";

const VAZIO: EmissorIn = {
  cnpj: "", razao_social: "", inscricao_municipal: null, municipio_ibge: "3106200", op_simp_nac: "1",
  reg_ap_trib_sn: null, reg_esp_trib: "0", serie_dps: "900", ambiente: "homologacao", ativo: false,
};

function doServidor(e: EmissorOut): EmissorIn {
  return {
    cnpj: e.cnpj ?? "", razao_social: e.razao_social ?? "", inscricao_municipal: e.inscricao_municipal,
    municipio_ibge: e.municipio_ibge ?? "3106200", op_simp_nac: e.op_simp_nac ?? "1", reg_ap_trib_sn: e.reg_ap_trib_sn,
    reg_esp_trib: e.reg_esp_trib ?? "0", serie_dps: e.serie_dps ?? "900", ambiente: "homologacao", ativo: e.ativo,
  };
}

export function AbaEmissor() {
  const [emissor, setEmissor] = useState<EmissorOut | null>(null);
  const [f, setF] = useState<EmissorIn>(VAZIO);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [pfx, setPfx] = useState<File | null>(null);
  const [senha, setSenha] = useState("");

  const carregar = useCallback(async () => {
    try {
      const e = await emissaoApi.emissor();
      setEmissor(e);
      if (e.configurado) setF(doServidor(e));
    } catch (err) {
      setAviso({ tipo: "erro", texto: mensagemDeErro(err) });
    }
  }, []);
  useEffect(() => { carregar(); }, [carregar]);

  const rodar = async (acao: () => Promise<EmissorOut>, ok: string) => {
    setOcupado(true);
    setAviso(null);
    try {
      const e = await acao();
      setEmissor(e);
      setF(doServidor(e));
      setAviso({ tipo: "ok", texto: ok });
    } catch (err) {
      setAviso({ tipo: "erro", texto: mensagemDeErro(err) });
    } finally {
      setOcupado(false);
    }
  };

  const salvar = (e: React.FormEvent) => {
    e.preventDefault();
    return rodar(() => emissaoApi.salvarEmissor({ ...f, cnpj: digitos(f.cnpj), reg_ap_trib_sn: f.op_simp_nac === "3" ? f.reg_ap_trib_sn ?? "1" : null }), "Dados do emissor salvos.");
  };
  const enviarCert = async () => {
    if (!pfx) return;
    await rodar(() => emissaoApi.enviarCertificado(pfx, senha), "Certificado guardado cifrado. O emissor foi desativado: ative de novo depois de conferir.");
    setSenha("");
    setPfx(null);
  };

  if (!emissor) return <p className="text-sm text-muted">Carregando…</p>;
  const set = <K extends keyof EmissorIn>(k: K, v: EmissorIn[K]) => setF((x) => ({ ...x, [k]: v }));

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-border bg-card p-4 text-sm">
        <strong>Ambiente: Homologação (produção restrita).</strong>{" "}
        <span className="text-muted">Nenhuma nota desta tela tem valor fiscal. Emissão em produção não está habilitada.</span>
      </div>
      {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}

      <form onSubmit={salvar} className="rounded-lg border border-border bg-card p-5 grid gap-4 sm:grid-cols-2">
        <h2 className="sm:col-span-2 font-display text-lg font-semibold text-primary-dark">Prestador e parâmetros fiscais</h2>
        <Campo rotulo="CNPJ do escritório"><input className={inputCls} value={f.cnpj} onChange={(e) => set("cnpj", e.target.value)} required inputMode="numeric" /></Campo>
        <Campo rotulo="Razão social"><input className={inputCls} value={f.razao_social} onChange={(e) => set("razao_social", e.target.value)} required /></Campo>
        <Campo rotulo="Inscrição municipal" dica="Obrigatória para BH (rejeição E0116 sem ela)."><input className={inputCls} value={f.inscricao_municipal ?? ""} onChange={(e) => set("inscricao_municipal", e.target.value || null)} /></Campo>
        <Campo rotulo="Código IBGE do município"><input className={inputCls} value={f.municipio_ibge} onChange={(e) => set("municipio_ibge", digitos(e.target.value))} maxLength={7} /></Campo>
        <Campo rotulo="Situação no Simples Nacional" dica="Confirme com o contador.">
          <select className={inputCls} value={f.op_simp_nac} onChange={(e) => set("op_simp_nac", e.target.value)}>
            {OPCOES_OP_SIMP_NAC.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </Campo>
        {f.op_simp_nac === "3" && (
          <Campo rotulo="Regime de apuração (ME/EPP)">
            <select className={inputCls} value={f.reg_ap_trib_sn ?? "1"} onChange={(e) => set("reg_ap_trib_sn", e.target.value)}>
              {OPCOES_REG_AP_TRIB_SN.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </Campo>
        )}
        <Campo rotulo="Regime especial de tributação">
          <select className={inputCls} value={f.reg_esp_trib} onChange={(e) => set("reg_esp_trib", e.target.value)}>
            {OPCOES_REG_ESP_TRIB.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </Campo>
        <Campo rotulo="Série da DPS"><input className={inputCls} value={f.serie_dps} onChange={(e) => set("serie_dps", digitos(e.target.value))} maxLength={5} /></Campo>
        <div className="sm:col-span-2 flex items-center gap-3">
          <button type="submit" disabled={ocupado} className={botaoPrimario}>{ocupado ? "Salvando…" : "Salvar"}</button>
        </div>
      </form>

      <section className="rounded-lg border border-border bg-card p-5 space-y-4" aria-labelledby="cert-titulo">
        <h2 id="cert-titulo" className="font-display text-lg font-semibold text-primary-dark">Certificado digital (A1)</h2>
        {emissor.tem_certificado ? (
          <p className="text-sm">
            Certificado guardado: <strong>{emissor.cert_titular}</strong>, válido até{" "}
            <strong>{emissor.cert_validade ? formatarData(emissor.cert_validade) : "—"}</strong>.
          </p>
        ) : (
          <p className="text-sm text-muted">Nenhum certificado enviado. Salve os dados do emissor primeiro.</p>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo rotulo="Arquivo .pfx"><input type="file" accept=".pfx,.p12" className={inputCls} onChange={(e) => setPfx(e.target.files?.[0] ?? null)} /></Campo>
          <Campo rotulo="Senha do certificado" dica="Fica cifrada no servidor e nunca é mostrada de novo."><input type="password" autoComplete="off" className={inputCls} value={senha} onChange={(e) => setSenha(e.target.value)} /></Campo>
        </div>
        <button onClick={enviarCert} disabled={ocupado || !pfx || !senha || !emissor.configurado} className={botaoSecundario}>Enviar certificado</button>
      </section>

      <section className="rounded-lg border border-border bg-card p-5 space-y-3" aria-labelledby="ativo-titulo">
        <h2 id="ativo-titulo" className="font-display text-lg font-semibold text-primary-dark">Ativação</h2>
        <p className="text-sm">
          Situação: <strong>{emissor.ativo ? "ativo" : "inativo"}</strong>. Só um emissor ativo, com certificado, emite notas.
        </p>
        <button
          onClick={() => rodar(() => emissaoApi.salvarEmissor({ ...f, cnpj: digitos(f.cnpj), reg_ap_trib_sn: f.op_simp_nac === "3" ? f.reg_ap_trib_sn ?? "1" : null, ativo: !emissor.ativo }), emissor.ativo ? "Emissor desativado." : "Emissor ativado.")}
          disabled={ocupado || !emissor.tem_certificado}
          className={botaoSecundario}
        >
          {emissor.ativo ? "Desativar emissor" : "Ativar emissor"}
        </button>
      </section>
    </div>
  );
}
