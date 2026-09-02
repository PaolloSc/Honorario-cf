"use client";

import { lookupCNPJ } from "@/app/lib/api";
import FormField, { Input, Select } from "@/components/ui/FormField";
import {
  contratantePJVazio,
  contratanteVazio,
  NACIONALIDADE_PADRAO,
  type ContratanteConsumidor,
  type ContratanteConsumidorPF,
  type ContratanteConsumidorPJ,
} from "@/types/consumidor";
import { useRef, useState } from "react";

function formatCPF(value: string): string {
  return value
    .replace(/\D/g, "")
    .slice(0, 11)
    .replace(/^(\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{3}\.\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{3}\.\d{3}\.\d{3})(\d)/, "$1-$2");
}

function formatCNPJ(value: string): string {
  return value
    .replace(/\D/g, "")
    .slice(0, 14)
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2}\.\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{2}\.\d{3}\.\d{3})(\d)/, "$1/$2")
    .replace(/^(\d{2}\.\d{3}\.\d{3}\/\d{4})(\d)/, "$1-$2");
}

function formatCEP(value: string): string {
  const d = value.replace(/\D/g, "").slice(0, 8);
  return d.length > 5 ? d.replace(/^(\d{5})(\d)/, "$1-$2") : d;
}

// (31) 9999-9999 e (31) 99999-9999 — o 9º digito muda a posicao do hifen.
function formatTelefone(value: string): string {
  const d = value.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d.replace(/^(\d{0,2})/, "($1");
  if (d.length <= 6) return d.replace(/^(\d{2})(\d+)/, "($1) $2");
  if (d.length <= 10) return d.replace(/^(\d{2})(\d{4})(\d+)/, "($1) $2-$3");
  return d.replace(/^(\d{2})(\d{5})(\d+)/, "($1) $2-$3");
}

// Monta a qualificacao do endereco na ordem usada nos contratos do escritorio.
function montarEndereco(c: ContratanteConsumidorPF): string {
  const cidadeUf = [c.cidade, c.uf].filter(Boolean).join("/");
  return [
    c.logradouro,
    c.numero ? `n.º ${c.numero}` : "",
    c.complemento,
    c.bairro,
    cidadeUf,
    c.cep ? `CEP: ${c.cep}` : "",
  ]
    .filter((p) => p && p.trim())
    .join(", ");
}

const GENEROS = [
  { value: "F", label: "Feminino (brasileira, inscrita)" },
  { value: "M", label: "Masculino (brasileiro, inscrito)" },
];

const SOMENTE_LEITURA = "bg-border/35 cursor-not-allowed text-muted";

interface Props {
  contratantes: ContratanteConsumidor[];
  onChange: (c: ContratanteConsumidor[]) => void;
}

export default function StepPartes({ contratantes, onChange }: Props) {
  const [buscando, setBuscando] = useState<number | null>(null);
  const [erroCep, setErroCep] = useState<Record<number, string>>({});
  const [erroCnpj, setErroCnpj] = useState<Record<number, string>>({});
  // Marcado quando o ViaCEP nao devolve rua (CEP unico de cidade). Fica ligado
  // enquanto o usuario digita — se dependesse do valor, o campo sumiria na 1a letra.
  const [precisaRua, setPrecisaRua] = useState<Record<number, boolean>>({});

  // A lista mais recente: as consultas sao assincronas e o estado muda no meio.
  const atual = useRef(contratantes);
  atual.current = contratantes;

  // Toda alteracao de PF remonta o endereco: ele nunca e' digitado direto.
  const update = (i: number, partial: Record<string, unknown>) => {
    onChange(
      atual.current.map((c, idx) => {
        if (idx !== i) return c;
        const novo = { ...c, ...partial } as ContratanteConsumidor;
        if (novo.tipo === "PF") return { ...novo, endereco: montarEndereco(novo) };
        return novo;
      })
    );
  };

  const trocarTipo = (i: number, tipo: "PF" | "PJ") => {
    if (contratantes[i].tipo === tipo) return;
    setPrecisaRua((prev) => ({ ...prev, [i]: false }));
    setErroCep((prev) => ({ ...prev, [i]: "" }));
    setErroCnpj((prev) => ({ ...prev, [i]: "" }));
    onChange(
      atual.current.map((c, idx) =>
        idx === i ? (tipo === "PF" ? contratanteVazio() : contratantePJVazio()) : c
      )
    );
  };

  const buscarCEP = async (i: number, valor: string) => {
    const cep = formatCEP(valor);
    update(i, { cep });
    const digitos = cep.replace(/\D/g, "");
    if (digitos.length !== 8) return;

    setBuscando(i);
    setErroCep((prev) => ({ ...prev, [i]: "" }));
    try {
      const res = await fetch(`https://viacep.com.br/ws/${digitos}/json/`);
      const data = await res.json();
      if (data.erro) {
        setErroCep((prev) => ({ ...prev, [i]: "CEP não encontrado." }));
        return;
      }
      update(i, {
        cep,
        logradouro: data.logradouro || "",
        bairro: data.bairro || "",
        cidade: data.localidade || "",
        uf: data.uf || "",
      });
      // CEP unico de cidade pequena vem sem rua/bairro — os campos ficam editaveis.
      setPrecisaRua((prev) => ({ ...prev, [i]: !data.logradouro }));
    } catch {
      setErroCep((prev) => ({ ...prev, [i]: "Erro ao buscar CEP." }));
    } finally {
      setBuscando(null);
    }
  };

  const buscarCNPJ = async (i: number, valor: string) => {
    const cnpj = formatCNPJ(valor);
    update(i, { cnpj });
    if (cnpj.replace(/\D/g, "").length !== 14) return;

    setBuscando(i);
    setErroCnpj((prev) => ({ ...prev, [i]: "" }));
    try {
      const res = await lookupCNPJ(cnpj);
      update(i, {
        cnpj,
        razao_social: res.razao_social.toUpperCase(),
        endereco: res.endereco,
      });
    } catch (e) {
      setErroCnpj((prev) => ({
        ...prev,
        [i]: `Consulta indisponível (${
          e instanceof Error ? e.message : "erro"
        }). Preencha razão social e endereço à mão.`,
      }));
    } finally {
      setBuscando(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Contratante(s)</h2>
        <p className="text-sm text-muted mt-1">
          Com dois ou mais contratantes o contrato inteiro vai para o plural automaticamente.
        </p>
      </div>

      {contratantes.map((c, i) => (
        <div key={i} className="border border-border rounded-xl p-5">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-medium">Contratante {i + 1}</h3>
            {contratantes.length > 1 && (
              <button
                type="button"
                onClick={() => onChange(contratantes.filter((_, idx) => idx !== i))}
                className="text-sm text-danger hover:underline"
              >
                Remover
              </button>
            )}
          </div>

          <div className="flex gap-2 mb-4">
            {(["PF", "PJ"] as const).map((tipo) => (
              <button
                key={tipo}
                type="button"
                onClick={() => trocarTipo(i, tipo)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                  c.tipo === tipo
                    ? "bg-primary text-white"
                    : "bg-background border border-border hover:border-primary/50"
                }`}
              >
                {tipo === "PF" ? "Pessoa Física" : "Pessoa Jurídica"}
              </button>
            ))}
          </div>

          {c.tipo === "PJ" ? (
            <>
              <FormField label="CNPJ" required hint="Digite para buscar razão social e endereço">
                <div className="flex gap-2">
                  <Input
                    value={c.cnpj}
                    onChange={(e) => buscarCNPJ(i, e.target.value)}
                    placeholder="00.000.000/0000-00"
                  />
                  {buscando === i && (
                    <span className="text-sm text-muted self-center whitespace-nowrap">...</span>
                  )}
                </div>
                {erroCnpj[i] && <p className="text-xs text-danger mt-1">{erroCnpj[i]}</p>}
              </FormField>

              <FormField label="Razão social" required>
                <Input
                  value={c.razao_social}
                  readOnly={!erroCnpj[i]}
                  tabIndex={erroCnpj[i] ? undefined : -1}
                  onChange={(e) => update(i, { razao_social: e.target.value.toUpperCase() })}
                  className={erroCnpj[i] ? "" : SOMENTE_LEITURA}
                  placeholder="Preenchida pelo CNPJ"
                />
              </FormField>

              <FormField label="Endereço da sede" required>
                <Input
                  value={c.endereco}
                  readOnly={!erroCnpj[i]}
                  tabIndex={erroCnpj[i] ? undefined : -1}
                  onChange={(e) => update(i, { endereco: e.target.value })}
                  className={erroCnpj[i] ? "" : SOMENTE_LEITURA}
                  placeholder="Preenchido pelo CNPJ"
                />
              </FormField>

              <FormField label="E-mail da empresa" hint="Opcional — entra na qualificação">
                <Input
                  type="email"
                  value={c.email ?? ""}
                  onChange={(e) => update(i, { email: e.target.value })}
                />
              </FormField>

              <div className="border-t border-border mt-5 pt-4">
                <h4 className="text-sm font-semibold mb-3">
                  Representante legal{" "}
                  <span className="font-normal text-muted">(quem assina pela empresa)</span>
                </h4>

                <FormField label="Nome do representante" required>
                  <Input
                    value={c.representante_nome}
                    onChange={(e) => update(i, { representante_nome: e.target.value })}
                  />
                </FormField>

                <div className="grid grid-cols-2 gap-4 items-end">
                  <FormField label="CPF do representante" required>
                    <Input
                      value={c.representante_cpf}
                      onChange={(e) =>
                        update(i, { representante_cpf: formatCPF(e.target.value) })
                      }
                      placeholder="000.000.000-00"
                    />
                  </FormField>

                  <FormField label="Gênero" required hint="Concordância: inscrita/inscrito">
                    <Select
                      value={c.representante_genero}
                      onChange={(e) =>
                        update(i, { representante_genero: e.target.value as "F" | "M" })
                      }
                      options={GENEROS}
                    />
                  </FormField>
                </div>

                <div className="grid grid-cols-2 gap-4 items-end">
                  <FormField label="Nacionalidade">
                    <Input
                      value={c.representante_nacionalidade}
                      onChange={(e) =>
                        update(i, { representante_nacionalidade: e.target.value })
                      }
                      placeholder={NACIONALIDADE_PADRAO}
                    />
                  </FormField>

                  <FormField
                    label="E-mail do representante"
                    hint="Opcional — recebe o contrato e o link de assinatura"
                  >
                    <Input
                      type="email"
                      value={c.representante_email ?? ""}
                      onChange={(e) => update(i, { representante_email: e.target.value })}
                    />
                  </FormField>
                </div>
              </div>
            </>
          ) : (
            <>
              <FormField label="Nome completo" required>
                <Input
                  value={c.nome}
                  onChange={(e) => update(i, { nome: e.target.value })}
                  placeholder="Nome como consta no documento"
                />
              </FormField>

              <div className="grid grid-cols-2 gap-4 items-end">
                <FormField
                  label="Gênero"
                  required
                  hint="Define a concordância: inscrita/inscrito"
                >
                  <Select
                    value={c.genero}
                    onChange={(e) => update(i, { genero: e.target.value as "F" | "M" })}
                    options={GENEROS}
                  />
                </FormField>

                <FormField label="CPF" required>
                  <Input
                    value={c.cpf}
                    onChange={(e) => update(i, { cpf: formatCPF(e.target.value) })}
                    placeholder="000.000.000-00"
                  />
                </FormField>
              </div>

              <div className="grid grid-cols-2 gap-4 items-end">
                <FormField label="RG" hint="Opcional — sai do contrato se vazio">
                  <Input value={c.rg ?? ""} onChange={(e) => update(i, { rg: e.target.value })} />
                </FormField>

                <FormField
                  label="Nacionalidade"
                  hint={`"${NACIONALIDADE_PADRAO}" vira brasileira/brasileiro no contrato`}
                >
                  <Input
                    value={c.nacionalidade}
                    onChange={(e) => update(i, { nacionalidade: e.target.value })}
                  />
                </FormField>
              </div>

              {/* items-end: as dicas tem alturas diferentes e desalinhariam os campos. */}
              <div className="grid grid-cols-3 gap-4 items-end">
                <FormField label="CEP" required hint="Monta o endereço">
                  <div className="flex gap-2">
                    <Input
                      value={c.cep ?? ""}
                      onChange={(e) => buscarCEP(i, e.target.value)}
                      placeholder="00000-000"
                    />
                    {buscando === i && (
                      <span className="text-sm text-muted self-center whitespace-nowrap">...</span>
                    )}
                  </div>
                  {erroCep[i] && <p className="text-xs text-danger mt-1">{erroCep[i]}</p>}
                </FormField>

                <FormField label="Número" required>
                  <Input
                    value={c.numero ?? ""}
                    onChange={(e) => update(i, { numero: e.target.value })}
                    placeholder="155E"
                  />
                </FormField>

                <FormField label="Complemento">
                  <Input
                    value={c.complemento ?? ""}
                    onChange={(e) => update(i, { complemento: e.target.value })}
                    placeholder="Apto. 803 / Interfone 05"
                  />
                </FormField>
              </div>

              {/* Bairro, cidade e UF vem do CEP e nao aparecem na tela.
                  Rua e bairro so' aparecem quando o CEP atende a cidade toda. */}
              {precisaRua[i] && (
                <div className="grid grid-cols-2 gap-4 items-end">
                  <FormField label="Logradouro" required hint="Este CEP atende a cidade toda">
                    <Input
                      value={c.logradouro ?? ""}
                      onChange={(e) => update(i, { logradouro: e.target.value })}
                      placeholder="Rua Major Egido Luiz Cerqueira"
                    />
                  </FormField>
                  <FormField label="Bairro" hint="Também não vem neste CEP">
                    <Input
                      value={c.bairro ?? ""}
                      onChange={(e) => update(i, { bairro: e.target.value })}
                      placeholder="Centro"
                    />
                  </FormField>
                </div>
              )}

              <FormField
                label="Endereço completo"
                hint="Montado automaticamente — ajuste pelo CEP, número e complemento"
              >
                <Input
                  value={c.endereco}
                  readOnly
                  tabIndex={-1}
                  className={SOMENTE_LEITURA}
                  placeholder="Preenchido pelo CEP"
                />
              </FormField>

              <div className="grid grid-cols-2 gap-4 items-end">
                <FormField label="E-mail" hint="Opcional — usado para envio e assinatura digital">
                  <Input
                    type="email"
                    value={c.email ?? ""}
                    onChange={(e) => update(i, { email: e.target.value })}
                  />
                </FormField>

                <FormField label="Celular" hint="Opcional">
                  <Input
                    value={c.celular ?? ""}
                    onChange={(e) => update(i, { celular: formatTelefone(e.target.value) })}
                    placeholder="(31) 99999-9999"
                  />
                </FormField>
              </div>
            </>
          )}
        </div>
      ))}

      <button
        type="button"
        onClick={() => onChange([...contratantes, contratanteVazio()])}
        className="px-4 py-2 border border-border rounded-lg text-sm font-medium hover:bg-background transition"
      >
        + Adicionar Contratante
      </button>
    </div>
  );
}
