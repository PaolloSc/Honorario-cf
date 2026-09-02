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
    nacionalidade: "Brasileiro(a)",
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
                  : "bg-background border border-border text-muted hover:border-primary/50"
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
                  : "bg-background border border-border text-muted hover:border-primary/50"
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
        <p className="text-sm text-danger mb-4">{cnpjError}</p>
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
  // Backend devolve null (nao undefined) quando nao ha representante — `!= null` cobre os dois.
  const temRepresentante = data.representante_nome != null;

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
            className="bg-border/35 border-muted text-muted cursor-not-allowed"
          />
        </FormField>
      )}

      {loaded && (
        <FormField label="Endereço">
          <Input
            value={data.endereco}
            readOnly
            placeholder="Preenchido automaticamente pelo CNPJ"
            className="bg-border/35 border-muted text-muted cursor-not-allowed"
          />
        </FormField>
      )}

      <div className="md:col-span-2">
        <Checkbox
          label="Adicionar dados do representante legal"
          checked={temRepresentante}
          onChange={(checked) => {
            if (!checked) {
              onUpdate({
                representante_nome: undefined,
                representante_cpf: undefined,
                representante_email: undefined,
                representante_nacionalidade: undefined,
                representante_profissao: undefined,
                representante_estado_civil: undefined,
              });
            } else {
              onUpdate({ representante_nome: "" });
            }
          }}
        />
      </div>

      {temRepresentante && (
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
                onUpdate({ representante_cpf: formatCPF(e.target.value) })
              }
              placeholder="000.000.000-00"
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

// Desmonta o endereco montado por buildEndereco para reidratar CEP/numero/complemento na edicao.
// Formato: "<logradouro>[, n. X][, <comp>], <bairro>, <cidade>/<UF>, CEP 00000-000"
function parseEndereco(endereco: string | undefined) {
  const vazio = { cep: "", numero: "", complemento: "" };
  const partes = (endereco || "").split(", ");
  const ultima = partes[partes.length - 1] || "";
  if (partes.length < 4 || !ultima.startsWith("CEP ")) return vazio;

  const meio = partes.slice(1, -3); // entre logradouro e bairro: numero e/ou complemento
  return {
    cep: formatCEP(ultima.replace(/\D/g, "").slice(0, 8)),
    numero: (meio.find((p) => p.startsWith("n. ")) || "").replace("n. ", ""),
    complemento: meio.filter((p) => !p.startsWith("n. ")).join(", "),
  };
}

function PFForm({
  data,
  onUpdate,
}: {
  data: ContratantePF;
  onUpdate: (partial: Partial<ContratantePF>) => void;
}) {
  const inicial = parseEndereco(data.endereco);
  const [cep, setCep] = useState(inicial.cep);
  const [numero, setNumero] = useState(inicial.numero);
  const [complemento, setComplemento] = useState(inicial.complemento);
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
          placeholder="Brasileiro(a)"
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
        {cepError && <p className="text-xs text-danger mt-1">{cepError}</p>}
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
            className="bg-border/35 border-muted text-muted cursor-not-allowed"
            required
          />
        </FormField>
      )}
    </div>
  );
}
