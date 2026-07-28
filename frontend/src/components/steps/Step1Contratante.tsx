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
  RepresentantePJ,
  TipoPessoa,
} from "@/types/contract";
import { useCallback, useState } from "react";

function toTitleCase(str: string): string {
  return str
    .toLowerCase()
    .replace(/(^|\s)\S/g, (char) => char.toUpperCase());
}

function formatCNPJ(digits: string): string {
  return digits
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2}\.\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{2}\.\d{3}\.\d{3})(\d)/, "$1/$2")
    .replace(/^(\d{2}\.\d{3}\.\d{3}\/\d{4})(\d)/, "$1-$2");
}

function formatCEP(digits: string): string {
  if (digits.length > 5) return digits.replace(/^(\d{5})(\d)/, "$1-$2");
  return digits;
}

function formatCPF(value: string): string {
  return value
    .replace(/\D/g, "")
    .slice(0, 11)
    .replace(/^(\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{3}\.\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{3}\.\d{3}\.\d{3})(\d)/, "$1-$2");
}

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
  const [cnpjLoaded, setCnpjLoaded] = useState<Set<number>>(new Set());
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
      setCnpjLoaded((prev) => {
        const next = new Set<number>();
        prev.forEach((i) => {
          if (i < index) next.add(i);
          else if (i > index) next.add(i - 1);
        });
        return next;
      });
      onChange(contratantes.filter((_, i) => i !== index));
    },
    [contratantes, onChange]
  );

  const switchTipo = useCallback(
    (index: number, tipo: TipoPessoa) => {
      setCnpjLoaded((prev) => {
        const next = new Set(prev);
        next.delete(index);
        return next;
      });
      setCNPJError(null);
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
        setCnpjLoaded((prev) => new Set(prev).add(index));
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
              loadingCNPJ={loadingCNPJ === idx}
              loaded={cnpjLoaded.has(idx) || (c.tipo === "PJ" && !!c.razao_social)}
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
  loadingCNPJ,
  loaded,
  onUpdate,
  onCNPJLookup,
}: {
  data: ContratantePJ;
  loadingCNPJ: boolean;
  loaded: boolean;
  onUpdate: (partial: Partial<ContratantePJ>) => void;
  onCNPJLookup: (cnpj: string) => void;
}) {
  // Contratos salvos antes da lista guardavam um unico representante em campos soltos.
  const reps: RepresentantePJ[] =
    data.representantes ??
    (data.representante_nome
      ? [{
          nome: data.representante_nome,
          nacionalidade: data.representante_nacionalidade,
          cpf: data.representante_cpf,
          profissao: data.representante_profissao,
          estado_civil: data.representante_estado_civil,
          email: data.representante_email,
        }]
      : []);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <FormField label="CNPJ" required hint="Digite o CNPJ para buscar dados automaticamente">
        <div className="flex gap-2">
          <Input
            value={formatCNPJ(data.cnpj)}
            onChange={(e) => {
              const digits = e.target.value.replace(/\D/g, "").slice(0, 14);
              onUpdate({ cnpj: digits });
            }}
            placeholder="00.000.000/0000-00"
            maxLength={18}
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

      {loaded && (
        <FormField label="Razão Social">
          <Input
            value={data.razao_social}
            readOnly
            placeholder="Preenchido automaticamente pelo CNPJ"
            className="bg-gray-50 cursor-not-allowed"
          />
        </FormField>
      )}

      {loaded && (
        <FormField label="Endereço">
          <Input
            value={data.endereco}
            readOnly
            placeholder="Preenchido automaticamente pelo CNPJ"
            className="bg-gray-50 cursor-not-allowed"
          />
        </FormField>
      )}

      <div className="md:col-span-2">
        <RepresentantesForm
          representantes={reps}
          onChange={(representantes) => onUpdate({ representantes })}
        />
      </div>
    </div>
  );
}

function emptyRepresentante(): RepresentantePJ {
  return { nome: "", nacionalidade: "Brasileira", profissao: "Empresário" };
}

function RepresentantesForm({
  representantes,
  onChange,
}: {
  representantes: RepresentantePJ[];
  onChange: (reps: RepresentantePJ[]) => void;
}) {
  const update = (i: number, partial: Partial<RepresentantePJ>) =>
    onChange(representantes.map((r, idx) => (idx === i ? { ...r, ...partial } : r)));

  return (
    <>
      <Checkbox
        label="Adicionar dados do(s) representante(s) legal(is)"
        checked={representantes.length > 0}
        onChange={(checked) => onChange(checked ? [emptyRepresentante()] : [])}
      />

      {representantes.map((rep, i) => (
        <div key={i} className="mt-4 border-l-2 border-primary-light pl-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-semibold text-foreground">
              Representante {i + 1}
            </p>
            {representantes.length > 1 && (
              <button
                type="button"
                onClick={() => onChange(representantes.filter((_, idx) => idx !== i))}
                className="text-danger text-sm hover:underline"
              >
                Remover
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FormField label="Nome do Representante">
              <Input value={rep.nome} onChange={(e) => update(i, { nome: e.target.value })} />
            </FormField>
            <FormField label="CPF do Representante">
              <Input
                value={rep.cpf || ""}
                onChange={(e) => update(i, { cpf: formatCPF(e.target.value) })}
                placeholder="000.000.000-00"
              />
            </FormField>
            <FormField label="E-mail do Representante">
              <Input
                type="email"
                value={rep.email || ""}
                onChange={(e) => update(i, { email: e.target.value })}
              />
            </FormField>
            <FormField label="Nacionalidade">
              <Input
                value={rep.nacionalidade || ""}
                onChange={(e) => update(i, { nacionalidade: e.target.value })}
              />
            </FormField>
            <FormField label="Profissão">
              <Input
                value={rep.profissao || ""}
                onChange={(e) => update(i, { profissao: e.target.value })}
              />
            </FormField>
            <FormField label="Estado Civil">
              <Select
                value={rep.estado_civil || ""}
                onChange={(e) => update(i, { estado_civil: e.target.value as EstadoCivil })}
                options={ESTADOS_CIVIS}
                placeholder="Selecione..."
              />
            </FormField>
          </div>
        </div>
      ))}

      {representantes.length > 0 && (
        <button
          type="button"
          onClick={() => onChange([...representantes, emptyRepresentante()])}
          className="mt-3 px-3 py-1.5 border border-dashed border-primary-light text-primary rounded-lg text-sm font-medium hover:bg-primary-light/20 transition"
        >
          + Adicionar representante
        </button>
      )}
    </>
  );
}

function PFForm({
  data,
  onUpdate,
}: {
  data: ContratantePF;
  onUpdate: (partial: Partial<ContratantePF>) => void;
}) {
  const [cep, setCep] = useState("");
  const [numero, setNumero] = useState("");
  const [complemento, setComplemento] = useState("");
  const [cepData, setCepData] = useState<{ logradouro: string; bairro: string; localidade: string; uf: string } | null>(null);
  const [loadingCEP, setLoadingCEP] = useState(false);
  const [cepError, setCepError] = useState<string | null>(null);

  const buildEndereco = (cData: typeof cepData, num: string, comp: string, cepValue: string = cep) => {
    if (!cData) return;
    const numPart = num ? `, n. ${num}` : "";
    const compPart = comp ? `, ${comp}` : "";
    const cepFormatado = cepValue.replace(/\D/g, "").replace(/(\d{5})(\d{3})/, "$1-$2");
    const endereco = `${cData.logradouro}${numPart}${compPart}, ${cData.bairro}, ${cData.localidade}/${cData.uf}, CEP ${cepFormatado}`;
    onUpdate({ endereco });
  };

  const handleCEPLookup = async (value: string) => {
    const digits = value.replace(/\D/g, "").slice(0, 8);
    setCep(formatCEP(digits));
    if (digits.length !== 8) return;

    setLoadingCEP(true);
    setCepError(null);
    try {
      const res = await fetch(`https://viacep.com.br/ws/${digits}/json/`);
      const result = await res.json();
      if (result.erro) {
        setCepError("CEP não encontrado.");
        return;
      }
      const cData = { logradouro: result.logradouro, bairro: result.bairro, localidade: result.localidade, uf: result.uf };
      setCepData(cData);
      buildEndereco(cData, numero, complemento, formatCEP(digits));
    } catch {
      setCepError("Erro ao buscar CEP.");
    } finally {
      setLoadingCEP(false);
    }
  };

  const handleNumeroChange = (value: string) => {
    setNumero(value);
    buildEndereco(cepData, value, complemento);
  };

  const handleComplementoChange = (value: string) => {
    setComplemento(value);
    buildEndereco(cepData, numero, value);
  };

  const enderecoRevelado = cepData != null || (data.endereco?.trim().length ?? 0) > 0;

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
          onChange={(e) => onUpdate({ cpf: formatCPF(e.target.value) })}
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

      <FormField label="CEP" hint="Digite o CEP para preencher o endereço">
        <div className="flex gap-2">
          <Input
            value={cep}
            onChange={(e) => handleCEPLookup(e.target.value)}
            placeholder="00000-000"
            maxLength={9}
          />
          {loadingCEP && <span className="text-sm text-muted self-center">Buscando...</span>}
        </div>
        {cepError && <p className="text-xs text-red-500 mt-1">{cepError}</p>}
      </FormField>

      {cepData && (
        <FormField label="Número">
          <Input
            value={numero}
            onChange={(e) => handleNumeroChange(e.target.value)}
            placeholder="Ex: 271"
          />
        </FormField>
      )}

      {cepData && (
        <FormField label="Complemento">
          <Input
            value={complemento}
            onChange={(e) => handleComplementoChange(e.target.value)}
            placeholder="Apto, sala, bloco..."
          />
        </FormField>
      )}

      {enderecoRevelado && (
        <FormField label="Endereço completo" required>
          <Input
            value={data.endereco}
            readOnly
            placeholder="Preenchido automaticamente pelo CEP"
            className="bg-gray-50 cursor-not-allowed"
            required
          />
        </FormField>
      )}
    </div>
  );
}
