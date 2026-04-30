"use client";

import FormField, {
  Checkbox,
  Input,
  Select,
} from "@/components/ui/FormField";
import { lookupCNPJ } from "@/app/lib/api";
import type {
  Contratante,
  ContratantePF,
  ContratantePJ,
  EstadoCivil,
  TipoPessoa,
} from "@/types/contract";
import { useCallback, useState } from "react";

const ESTADOS_CIVIS: Array<{ value: EstadoCivil; label: string }> = [
  { value: "Solteiro(a)", label: "Solteiro(a)" },
  { value: "Casado(a)", label: "Casado(a)" },
  { value: "Divorciado(a)", label: "Divorciado(a)" },
  { value: "Viúvo(a)", label: "Viúvo(a)" },
  { value: "União Estável", label: "União Estável" },
  { value: "Separado(a)", label: "Separado(a)" },
];

function emptyPF(): ContratantePF {
  return {
    tipo: "PF",
    nome: "",
    nacionalidade: "Brasileira",
    cpf: "",
    profissao: "",
    estado_civil: "Solteiro(a)",
    endereco: "",
    email: "",
  };
}

function emptyPJ(): ContratantePJ {
  return {
    tipo: "PJ",
    cnpj: "",
    razao_social: "",
    endereco: "",
    email: "",
  };
}

interface Step1Props {
  contratantes: Contratante[];
  onChange: (contratantes: Contratante[]) => void;
}

export default function Step1Contratante({
  contratantes,
  onChange,
}: Step1Props) {
  const [loadingCNPJ, setLoadingCNPJ] = useState<number | null>(null);
  const [cnpjError, setCNPJError] = useState<string | null>(null);

  const updateContratante = useCallback(
    (index: number, partial: Partial<Contratante>) => {
      const updated = [...contratantes];
      updated[index] = { ...updated[index], ...partial } as Contratante;
      onChange(updated);
    },
    [contratantes, onChange]
  );

  const addContratante = useCallback(() => {
    onChange([...contratantes, emptyPF()]);
  }, [contratantes, onChange]);

  const removeContratante = useCallback(
    (index: number) => {
      if (contratantes.length <= 1) return;
      onChange(contratantes.filter((_, i) => i !== index));
    },
    [contratantes, onChange]
  );

  const switchTipo = useCallback(
    (index: number, tipo: TipoPessoa) => {
      const updated = [...contratantes];
      updated[index] = tipo === "PF" ? emptyPF() : emptyPJ();
      onChange(updated);
    },
    [contratantes, onChange]
  );

  const handleCNPJLookup = useCallback(
    async (index: number, cnpj: string) => {
      const digits = cnpj.replace(/\D/g, "");
      if (digits.length !== 14) {
        setCNPJError(
          `CNPJ deve ter 14 dígitos (informados: ${digits.length}).`
        );
        return;
      }
      setLoadingCNPJ(index);
      setCNPJError(null);
      try {
        const data = await lookupCNPJ(cnpj);
        updateContratante(index, {
          razao_social: data.razao_social,
          endereco: data.endereco,
        });
      } catch (err) {
        console.error("[CNPJ Lookup] Error:", err);
        const msg = err instanceof Error ? err.message : "erro desconhecido";
        setCNPJError(`CNPJ não encontrado ou erro na consulta: ${msg}. Preencha manualmente.`);
      } finally {
        setLoadingCNPJ(null);
      }
    },
    [updateContratante]
  );

  return (
    <div>
      <h2 className="text-xl font-bold text-primary mb-2">
        1. Qualificação da(s) Contratante(s)
      </h2>
      <p className="text-sm text-muted mb-6">
        Informe os dados de cada contratante. Para PJ, o CNPJ será consultado na
        Receita Federal automaticamente.
      </p>

      {contratantes.map((c, idx) => (
        <div
          key={idx}
          className="bg-card border border-border rounded-xl p-6 mb-4 shadow-sm"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-foreground">
              Contratante {idx + 1}
            </h3>
            {contratantes.length > 1 && (
              <button
                type="button"
                onClick={() => removeContratante(idx)}
                className="text-danger text-sm hover:underline"
              >
                Remover
              </button>
            )}
          </div>

          <div className="flex gap-4 mb-4">
            <button
              type="button"
              onClick={() => switchTipo(idx, "PF")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                c.tipo === "PF"
                  ? "bg-primary text-white"
                  : "bg-gray-100 text-muted hover:bg-gray-200"
              }`}
            >
              Pessoa Física
            </button>
            <button
              type="button"
              onClick={() => switchTipo(idx, "PJ")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                c.tipo === "PJ"
                  ? "bg-primary text-white"
                  : "bg-gray-100 text-muted hover:bg-gray-200"
              }`}
            >
              Pessoa Jurídica
            </button>
          </div>

          {c.tipo === "PJ" ? (
            <PJForm
              data={c}
              index={idx}
              loadingCNPJ={loadingCNPJ === idx}
              onUpdate={(partial) => updateContratante(idx, partial)}
              onCNPJLookup={(cnpj) => handleCNPJLookup(idx, cnpj)}
            />
          ) : (
            <PFForm
              data={c}
              onUpdate={(partial) => updateContratante(idx, partial)}
            />
          )}
        </div>
      ))}

      <button
        type="button"
        onClick={addContratante}
        className="mb-6 px-4 py-2 border-2 border-dashed border-primary-light text-primary rounded-lg text-sm font-medium hover:bg-primary-light/20 transition w-full"
      >
        + Adicionar Contratante
      </button>

      {cnpjError && (
        <p className="text-sm text-red-500 mb-4">{cnpjError}</p>
      )}
    </div>
  );
}

function PJForm({
  data,
  index,
  loadingCNPJ,
  onUpdate,
  onCNPJLookup,
}: {
  data: ContratantePJ;
  index: number;
  loadingCNPJ: boolean;
  onUpdate: (partial: Partial<ContratantePJ>) => void;
  onCNPJLookup: (cnpj: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <FormField label="CNPJ" required hint="Digite o CNPJ para buscar dados automaticamente">
        <div className="flex gap-2">
          <Input
            value={data.cnpj}
            onChange={(e) => onUpdate({ cnpj: e.target.value })}
            placeholder="00.000.000/0000-00"
            required
          />
          <button
            type="button"
            onClick={() => onCNPJLookup(data.cnpj)}
            disabled={loadingCNPJ}
            className="px-3 py-2 bg-primary text-white text-sm rounded-lg hover:bg-primary-dark transition disabled:opacity-50 whitespace-nowrap"
          >
            {loadingCNPJ ? "Buscando..." : "Buscar"}
          </button>
        </div>
      </FormField>

      <FormField label="E-mail de contato" required>
        <Input
          type="email"
          value={data.email}
          onChange={(e) => onUpdate({ email: e.target.value })}
          placeholder="contato@empresa.com"
          required
        />
      </FormField>

      <FormField label="Razão Social">
        <Input
          value={data.razao_social}
          onChange={(e) => onUpdate({ razao_social: e.target.value })}
          placeholder="Preenchido automaticamente pelo CNPJ"
        />
      </FormField>

      <FormField label="Endereço">
        <Input
          value={data.endereco}
          onChange={(e) => onUpdate({ endereco: e.target.value })}
          placeholder="Preenchido automaticamente pelo CNPJ"
        />
      </FormField>

      <div className="md:col-span-2">
        <Checkbox
          label="Adicionar dados do representante legal"
          checked={data.representante_nome !== undefined}
          onChange={(checked) => {
            if (!checked) {
              onUpdate({
                representante_nome: undefined,
                representante_cpf: undefined,
                representante_email: undefined,
              });
            } else {
              onUpdate({ representante_nome: "" });
            }
          }}
        />
      </div>

      {data.representante_nome !== undefined && (
        <>
          <FormField label="Nome do Representante">
            <Input
              value={data.representante_nome || ""}
              onChange={(e) =>
                onUpdate({ representante_nome: e.target.value })
              }
            />
          </FormField>
          <FormField label="CPF do Representante">
            <Input
              value={data.representante_cpf || ""}
              onChange={(e) =>
                onUpdate({ representante_cpf: e.target.value })
              }
            />
          </FormField>
          <FormField label="E-mail do Representante">
            <Input
              type="email"
              value={data.representante_email || ""}
              onChange={(e) =>
                onUpdate({ representante_email: e.target.value })
              }
            />
          </FormField>
          <FormField label="Nacionalidade">
            <Input
              value={data.representante_nacionalidade || ""}
              onChange={(e) =>
                onUpdate({
                  representante_nacionalidade: e.target.value,
                })
              }
            />
          </FormField>
          <FormField label="Profissão">
            <Input
              value={data.representante_profissao || ""}
              onChange={(e) =>
                onUpdate({ representante_profissao: e.target.value })
              }
            />
          </FormField>
          <FormField label="Estado Civil">
            <Select
              value={data.representante_estado_civil || ""}
              onChange={(e) =>
                onUpdate({
                  representante_estado_civil: e.target.value as EstadoCivil,
                })
              }
              options={ESTADOS_CIVIS}
              placeholder="Selecione..."
            />
          </FormField>
        </>
      )}
    </div>
  );
}

function PFForm({
  data,
  onUpdate,
}: {
  data: ContratantePF;
  onUpdate: (partial: Partial<ContratantePF>) => void;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <FormField label="Nome completo" required>
        <Input
          value={data.nome}
          onChange={(e) => onUpdate({ nome: e.target.value })}
          placeholder="Nome completo"
          required
        />
      </FormField>

      <FormField label="CPF" required>
        <Input
          value={data.cpf}
          onChange={(e) => onUpdate({ cpf: e.target.value })}
          placeholder="000.000.000-00"
          required
        />
      </FormField>

      <FormField label="Nacionalidade">
        <Input
          value={data.nacionalidade}
          onChange={(e) => onUpdate({ nacionalidade: e.target.value })}
          placeholder="Brasileira"
        />
      </FormField>

      <FormField label="Profissão">
        <Input
          value={data.profissao}
          onChange={(e) => onUpdate({ profissao: e.target.value })}
          placeholder="Profissão"
        />
      </FormField>

      <FormField label="Estado Civil" required>
        <Select
          value={data.estado_civil}
          onChange={(e) =>
            onUpdate({ estado_civil: e.target.value as EstadoCivil })
          }
          options={ESTADOS_CIVIS}
          placeholder="Selecione..."
          required
        />
      </FormField>

      <FormField label="E-mail" required>
        <Input
          type="email"
          value={data.email}
          onChange={(e) => onUpdate({ email: e.target.value })}
          placeholder="email@exemplo.com"
          required
        />
      </FormField>

      <FormField label="Endereço completo" required>
        <Input
          value={data.endereco}
          onChange={(e) => onUpdate({ endereco: e.target.value })}
          placeholder="Rua, número, bairro, cidade/UF, CEP"
          className="md:col-span-2"
          required
        />
      </FormField>
    </div>
  );
}
