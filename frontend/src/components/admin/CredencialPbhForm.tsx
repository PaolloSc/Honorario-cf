"use client";

import { useEffect, useState } from "react";
import { credencialApi, type CredencialPbhOut } from "@/app/lib/nfse-api";

export function CredencialPbhPanel() {
  const [items, setItems] = useState<CredencialPbhOut[]>([]);
  const [form, setForm] = useState({ cnpj_prestador: "", login: "", senha: "" });
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = () => credencialApi.listar().then(setItems).catch((e) => setErr(String(e)));
  useEffect(() => { refresh(); }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setErr("");
    try {
      await credencialApi.upsert(form);
      setForm({ cnpj_prestador: "", login: "", senha: "" });
      refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "erro");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="bg-card border border-border rounded-lg p-4 space-y-3 text-sm">
        <h3 className="font-medium">Nova / atualizar credencial</h3>
        <div className="grid md:grid-cols-3 gap-3">
          <label>
            <span className="block text-xs text-muted">CNPJ prestador (só dígitos)</span>
            <input required value={form.cnpj_prestador}
                   onChange={(e) => setForm({ ...form, cnpj_prestador: e.target.value })}
                   className="w-full px-2 py-1 border border-border rounded font-mono"/>
          </label>
          <label>
            <span className="block text-xs text-muted">Login BHISS</span>
            <input required value={form.login}
                   onChange={(e) => setForm({ ...form, login: e.target.value })}
                   className="w-full px-2 py-1 border border-border rounded"/>
          </label>
          <label>
            <span className="block text-xs text-muted">Senha</span>
            <input required type="password" value={form.senha}
                   onChange={(e) => setForm({ ...form, senha: e.target.value })}
                   className="w-full px-2 py-1 border border-border rounded"/>
          </label>
        </div>
        {err && <div className="text-xs text-red-700">{err}</div>}
        <button disabled={saving}
                className="px-3 py-1.5 bg-primary-dark text-white rounded text-xs disabled:opacity-50">
          {saving ? "Salvando..." : "Salvar credencial"}
        </button>
        <p className="text-xs text-muted">
          Senha é criptografada em repouso (AES-GCM). Nunca aparece em logs ou listagens.
        </p>
      </form>

      <div className="space-y-2">
        <h3 className="font-medium text-sm">Credenciais ativas</h3>
        {items.length === 0 ? (
          <p className="text-xs text-muted">Nenhuma credencial cadastrada.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs text-muted border-b border-border">
              <tr>
                <th className="text-left py-2">CNPJ</th>
                <th className="text-left py-2">Status</th>
                <th className="text-left py-2">Cadastrado por</th>
                <th className="text-left py-2">Em</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} className="border-b border-border/40">
                  <td className="py-2 font-mono text-xs">{c.cnpj_prestador}</td>
                  <td className="py-2">
                    <span className={c.ativo
                        ? "text-green-700 text-xs"
                        : "text-red-700 text-xs"}>
                      {c.ativo ? "ativo" : `inativo${c.motivo_inativacao ? " · " + c.motivo_inativacao : ""}`}
                    </span>
                  </td>
                  <td className="py-2 text-xs">{c.criado_por}</td>
                  <td className="py-2 text-xs">{new Date(c.criado_em).toLocaleString("pt-BR")}</td>
                  <td className="py-2 text-right">
                    {c.ativo && (
                      <button
                        onClick={async () => {
                          if (!confirm("Desativar credencial?")) return;
                          await credencialApi.desativar(c.cnpj_prestador, "manual");
                          refresh();
                        }}
                        className="text-xs text-red-700 hover:underline"
                      >
                        Desativar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
