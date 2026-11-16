"use client";

import { useState } from "react";
import { updateTestemunha, type Testemunha } from "@/app/lib/api";
import { formatCPF, isValidCPF } from "@/app/lib/cpf";
import { ComboBox } from "@/components/ui/FormField";

const campo =
  "px-3 py-1.5 border border-border bg-card text-foreground rounded text-sm focus:outline-none focus:ring-1 focus:ring-primary/40";

// Linha "nome + e-mail + CPF + Adicionar" das testemunhas do envio para assinatura.
// O CPF é obrigatório e sai sob a assinatura da testemunha no documento. Quem está no
// cadastro sem CPF tem o CPF gravado lá; quem já tem usa o do cadastro, que é a fonte.
export default function AdicionarTestemunha({
  roster,
  onRosterChange,
  onDoCadastro,
  onAvulsa,
}: {
  roster: Testemunha[];
  onRosterChange: (roster: Testemunha[]) => void;
  onDoCadastro: (id: number) => void;
  onAvulsa: (t: { email: string; name: string; cpf: string }) => void;
}) {
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [cpf, setCpf] = useState("");
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  const adicionar = async () => {
    const n = nome.trim();
    const e = email.trim();
    if (!n || !e) return;
    const match = roster.find((t) => t.nome.trim().toLowerCase() === n.toLowerCase());
    // Quem já tem CPF no cadastro usa o do cadastro (corrigir é lá, em Testemunhas).
    if (!match?.cpf && !isValidCPF(cpf)) return setErro("CPF da testemunha inválido.");
    setErro("");
    if (match) {
      if (!match.cpf) {
        setSalvando(true);
        try {
          const salvo = await updateTestemunha(match.id, { cpf });
          onRosterChange(roster.map((t) => (t.id === salvo.id ? salvo : t)));
        } catch {
          return setErro("Não foi possível gravar o CPF no cadastro de testemunhas. Tente de novo.");
        } finally {
          setSalvando(false);
        }
      }
      onDoCadastro(match.id);
    } else {
      onAvulsa({ email: e, name: n, cpf });
    }
    setNome("");
    setEmail("");
    setCpf("");
  };

  return (
    <>
      <div className="flex flex-wrap gap-2">
        <ComboBox
          livre
          className="flex-1 min-w-40"
          value={nome}
          options={roster.map((t) => ({ value: t.nome, label: t.nome }))}
          onChange={(v) => {
            setNome(v);
            const t = roster.find((x) => x.nome === v);
            if (t) {
              setEmail(t.email);
              setCpf(t.cpf || "");
            }
          }}
          placeholder="Busque por nome ou digite uma testemunha avulsa"
        />
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="email@exemplo.com"
          className={`flex-1 min-w-48 ${campo}`}
        />
        <input
          type="text"
          inputMode="numeric"
          required
          aria-label="CPF da testemunha (obrigatório)"
          value={cpf}
          onChange={(e) => setCpf(formatCPF(e.target.value))}
          readOnly={Boolean(roster.find((t) => t.nome === nome)?.cpf)}
          title="CPF do Cadastro de Testemunhas; para corrigir, edite lá"
          placeholder="CPF (obrigatório)"
          className={`w-40 ${campo}`}
        />
        <button
          type="button"
          onClick={() => void adicionar()}
          disabled={salvando || !nome.trim() || !email.trim() || !cpf.trim()}
          className="shrink-0 px-3 py-1.5 bg-accent text-white text-sm rounded hover:opacity-90 disabled:opacity-50 transition"
        >
          Adicionar
        </button>
      </div>
      {erro && <p className="mt-2 text-xs text-danger">{erro}</p>}
    </>
  );
}

/** CPF ao lado do nome na lista de testemunhas escolhidas; sem CPF o envio é recusado. */
export function CpfDaTestemunha({ cpf }: { cpf?: string }) {
  return cpf ? (
    <span className="text-muted">CPF {cpf}</span>
  ) : (
    <em className="text-danger">sem CPF: remova e adicione de novo, informando o CPF</em>
  );
}
