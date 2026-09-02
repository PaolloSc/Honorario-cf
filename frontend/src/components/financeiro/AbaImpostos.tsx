"use client";

import { useCallback, useEffect, useState } from "react";
import { taxCodeApi, type TaxCode, type TaxCodeCreate } from "@/app/lib/finance-api";

const EMPTY: TaxCodeCreate = {
  codigo: "",
  descricao: "",
  aliquota_total: 0,
  aliquota_iss: 0,
  aliquota_pis: 0,
  aliquota_cofins: 0,
  aliquota_irrf: 0,
  aliquota_csll: 0,
};

function pct(v: number) {
  return `${(v * 100).toFixed(2)}%`;
}

export function AbaImpostos() {
  const [items, setItems] = useState<TaxCode[]>([]);
  const [form, setForm] = useState<TaxCodeCreate>(EMPTY);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    taxCodeApi
      .listar(true)
      .then(setItems)
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const total =
      form.aliquota_iss +
      form.aliquota_pis +
      form.aliquota_cofins +
      form.aliquota_irrf +
      form.aliquota_csll;
    setForm((f) => ({ ...f, aliquota_total: Number(total.toFixed(4)) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    form.aliquota_iss,
    form.aliquota_pis,
    form.aliquota_cofins,
    form.aliquota_irrf,
    form.aliquota_csll,
  ]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      if (editingId) {
        await taxCodeApi.atualizar(editingId, form);
      } else {
        await taxCodeApi.criar(form);
      }
      setForm(EMPTY);
      setEditingId(null);
      refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "erro");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (tc: TaxCode) => {
    setForm({
      codigo: tc.codigo,
      descricao: tc.descricao,
      aliquota_total: tc.aliquota_total,
      aliquota_iss: tc.aliquota_iss,
      aliquota_pis: tc.aliquota_pis,
      aliquota_cofins: tc.aliquota_cofins,
      aliquota_irrf: tc.aliquota_irrf,
      aliquota_csll: tc.aliquota_csll,
    });
    setEditingId(tc.id);
  };

  const cancelEdit = () => {
    setForm(EMPTY);
    setEditingId(null);
  };

  const desativar = async (tc: TaxCode) => {
    if (!confirm(`Desativar ${tc.codigo}?`)) return;
    try {
      await taxCodeApi.desativar(tc.id);
      refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "erro");
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="bg-card border border-border rounded-lg p-4 space-y-3 text-sm">
        <h3 className="font-medium">{editingId ? "Editar Tax Code" : "Novo Tax Code"}</h3>
        <div className="grid md:grid-cols-2 gap-3">
          <label>
            <span className="block text-xs text-muted">Código</span>
            <input
              required
              disabled={!!editingId}
              value={form.codigo}
              onChange={(e) => setForm({ ...form, codigo: e.target.value })}
              className="w-full px-2 py-1 border border-border rounded font-mono uppercase"
            />
          </label>
          <label>
            <span className="block text-xs text-muted">Descrição</span>
            <input
              required
              value={form.descricao}
              onChange={(e) => setForm({ ...form, descricao: e.target.value })}
              className="w-full px-2 py-1 border border-border rounded"
            />
          </label>
        </div>
        <div className="grid grid-cols-5 gap-2">
          {(["iss", "pis", "cofins", "irrf", "csll"] as const).map((k) => (
            <label key={k}>
              <span className="block text-xs text-muted uppercase">{k}</span>
              <input
                type="number"
                step={0.0001}
                min={0}
                max={1}
                value={form[`aliquota_${k}` as const]}
                onChange={(e) =>
                  setForm({ ...form, [`aliquota_${k}`]: parseFloat(e.target.value) || 0 })
                }
                className="w-full px-2 py-1 border border-border rounded"
              />
            </label>
          ))}
        </div>
        <p className="text-xs text-muted">
          Alíquota total (soma):{" "}
          <strong className="text-foreground">{pct(form.aliquota_total)}</strong>
        </p>
        {err && <div className="text-xs text-danger">{err}</div>}
        <div className="flex gap-2">
          <button
            disabled={saving}
            className="px-3 py-1.5 bg-primary-dark text-white rounded text-xs disabled:opacity-50"
          >
            {saving ? "Salvando..." : editingId ? "Salvar alterações" : "Criar"}
          </button>
          {editingId && (
            <button
              type="button"
              onClick={cancelEdit}
              className="px-3 py-1.5 border border-border rounded text-xs"
            >
              Cancelar
            </button>
          )}
        </div>
      </form>

      <div>
        <h3 className="font-medium text-sm mb-2">Tax Codes cadastrados</h3>
        {loading ? (
          <p className="text-muted text-xs">Carregando...</p>
        ) : items.length === 0 ? (
          <p className="text-muted text-xs">Nenhum cadastrado.</p>
        ) : (
          <table className="w-full text-xs">
            <thead className="text-muted border-b border-border">
              <tr>
                <th className="text-left py-2">Código</th>
                <th className="text-left py-2">Descrição</th>
                <th className="text-right py-2">Total</th>
                <th className="text-right py-2">ISS</th>
                <th className="text-right py-2">PIS</th>
                <th className="text-right py-2">COFINS</th>
                <th className="text-right py-2">IRRF</th>
                <th className="text-right py-2">CSLL</th>
                <th className="text-left py-2">Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((tc) => (
                <tr key={tc.id} className="border-b border-border/40">
                  <td className="py-2 font-mono">{tc.codigo}</td>
                  <td className="py-2">{tc.descricao}</td>
                  <td className="py-2 text-right">{pct(tc.aliquota_total)}</td>
                  <td className="py-2 text-right">{pct(tc.aliquota_iss)}</td>
                  <td className="py-2 text-right">{pct(tc.aliquota_pis)}</td>
                  <td className="py-2 text-right">{pct(tc.aliquota_cofins)}</td>
                  <td className="py-2 text-right">{pct(tc.aliquota_irrf)}</td>
                  <td className="py-2 text-right">{pct(tc.aliquota_csll)}</td>
                  <td className="py-2">
                    {tc.ativo ? (
                      <span className="text-primary-dark">ativo</span>
                    ) : (
                      <span className="text-danger">inativo</span>
                    )}
                  </td>
                  <td className="py-2 text-right space-x-2">
                    <button
                      onClick={() => startEdit(tc)}
                      className="text-xs text-accent hover:underline"
                    >
                      Editar
                    </button>
                    {tc.ativo && (
                      <button
                        onClick={() => desativar(tc)}
                        className="text-xs text-danger hover:underline"
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
