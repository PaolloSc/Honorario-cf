"use client";

import FormField, {
  Checkbox,
  Input,
  Select,
} from "@/components/ui/FormField";
import { lookupCNPJ, sugerirClientes, type SocioReceita, type SugestaoCliente } from "@/app/lib/api";
import { cnpjValido, formatarCNPJ, limparCNPJ } from "@/app/lib/cnpj";
import type {
  Contratante,
  ContratantePF,
  ContratantePJ,
  EstadoCivil,
  RepresentantePJ,
  TipoPessoa,
} from "@/types/contract";
import { useCallback, useEffect, useState } from "react";

function toTitleCase(str: string): string {
  return str
    .toLowerCase()
    .replace(/(^|\s)\S/g, (char) => char.toUpperCase());
}

function formatCEP(digits: string): string {
  if (digits.length > 5) return digits.replace(/^(\d{5})(\d)/, "$1-$2");
  return digits;
}

// (31) 9999-9999 e (31) 99999-9999 — o 9º digito muda a posicao do hifen.
function formatTelefone(value: string): string {
  const d = value.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d.replace(/^(\d{0,2})/, "($1");
  if (d.length <= 6) return d.replace(/^(\d{2})(\d+)/, "($1) $2");
  if (d.length <= 10) return d.replace(/^(\d{2})(\d{4})(\d+)/, "($1) $2-$3");
  return d.replace(/^(\d{2})(\d{5})(\d+)/, "($1) $2-$3");
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

// "2026-03-05T12:00:00" -> "05/03/2026" (sem passar por Date: evita virar o dia no fuso).
function dataBR(iso: string): string {
  return iso.slice(0, 10).split("-").reverse().join("/");
}

function formatDoc(doc: string): string {
  return doc.length === 11 ? formatCPF(doc) : formatarCNPJ(doc);
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
  // Consulta falhou (API fora, CNPJ novo/alfanumérico ainda não indexado): libera a digitação.
  const [cnpjManual, setCnpjManual] = useState<Set<number>>(new Set());
  const [cnpjError, setCNPJError] = useState<string | null>(null);
  // Card preenchido com cliente já atendido -> data do contrato de origem (aviso "confira").
  const [origem, setOrigem] = useState<Record<number, string>>({});
  // Dados da Receita que não vão para o contrato: chaveado pelo CNPJ, some sozinho se ele mudar.
  const [receita, setReceita] = useState<
    Record<string, { situacao: string; socios: SocioReceita[] }>
  >({});

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
      const reindexar = (prev: Set<number>) => {
        const next = new Set<number>();
        prev.forEach((i) => {
          if (i < index) next.add(i);
          else if (i > index) next.add(i - 1);
        });
        return next;
      };
      setCnpjLoaded(reindexar);
      setCnpjManual(reindexar);
      setOrigem((prev) => {
        const next: Record<number, string> = {};
        for (const [k, v] of Object.entries(prev)) {
          const i = Number(k);
          if (i < index) next[i] = v;
          else if (i > index) next[i - 1] = v;
        }
        return next;
      });
      onChange(contratantes.filter((_, i) => i !== index));
    },
    [contratantes, onChange]
  );

  const switchTipo = useCallback(
    (index: number, tipo: TipoPessoa) => {
      const remover = (prev: Set<number>) => {
        const next = new Set(prev);
        next.delete(index);
        return next;
      };
      setCnpjLoaded(remover);
      setCnpjManual(remover);
      setCNPJError(null);
      setOrigem(({ [index]: _, ...resto }) => resto);
      const updated = [...contratantes];
      updated[index] = tipo === "PF" ? emptyPF() : emptyPJ();
      onChange(updated);
    },
    [contratantes, onChange]
  );

  const usarSugestao = useCallback(
    (index: number, s: SugestaoCliente) => {
      const remover = (prev: Set<number>) => {
        const next = new Set(prev);
        next.delete(index);
        return next;
      };
      // Sem "travado pela Receita": o dado veio de contrato antigo e precisa ficar editável.
      setCnpjLoaded(remover);
      setCnpjManual(remover);
      setCNPJError(null);
      setOrigem((prev) => ({ ...prev, [index]: dataBR(s.data_contrato) }));
      const base = s.contratante.tipo === "PJ" ? emptyPJ() : emptyPF();
      const updated = [...contratantes];
      updated[index] = { ...base, ...s.contratante } as Contratante;
      onChange(updated);
    },
    [contratantes, onChange]
  );

  const handleCNPJLookup = useCallback(
    async (index: number, cnpj: string) => {
      if (!cnpjValido(cnpj)) {
        setCNPJError("CNPJ inválido: confira os 14 caracteres e os dígitos verificadores.");
        return;
      }
      setLoadingCNPJ(index);
      setCNPJError(null);
      try {
        const data = await lookupCNPJ(cnpj);
        setReceita((prev) => ({
          ...prev,
          [limparCNPJ(cnpj)]: { situacao: data.situacao_cadastral || "", socios: data.socios ?? [] },
        }));
        updateContratante(index, {
          razao_social: data.razao_social,
          endereco: data.endereco,
        });
        setCnpjLoaded((prev) => new Set(prev).add(index));
        setCnpjManual((prev) => {
          const next = new Set(prev);
          next.delete(index);
          return next;
        });
      } catch (err) {
        console.error("[CNPJ Lookup] Error:", err);
        const msg = err instanceof Error ? err.message : "erro desconhecido";
        setCNPJError(`CNPJ não encontrado ou erro na consulta: ${msg}. Preencha a razão social e o endereço manualmente.`);
        setCnpjManual((prev) => new Set(prev).add(index));
        // Razão social/endereço de OUTRO CNPJ (consulta anterior) não podem sobrar no
        // contrato do novo; o que foi digitado à mão fica.
        if (cnpjLoaded.has(index)) updateContratante(index, { razao_social: "", endereco: "" });
        setCnpjLoaded((prev) => {
          const next = new Set(prev);
          next.delete(index);
          return next;
        });
      } finally {
        setLoadingCNPJ(null);
      }
    },
    [updateContratante, cnpjLoaded]
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

          <ClienteRecorrente onEscolher={(s) => usarSugestao(idx, s)} />
          {origem[idx] && (
            <p className="text-xs text-warning bg-warning/10 border border-warning/30 rounded-lg px-3 py-2 mb-4">
              Dados de {origem[idx]}, de um contrato anterior: confira endereço, estado civil e contatos.
            </p>
          )}

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
              loaded={cnpjLoaded.has(idx) || cnpjManual.has(idx) || (c.tipo === "PJ" && !!c.razao_social)}
              // Só trava o que a Receita acabou de devolver; rascunho/edição trazem o
              // valor salvo (que pode ter sido digitado) e precisam continuar editáveis.
              editavel={!cnpjLoaded.has(idx)}
              receita={receita[c.cnpj]}
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

// Busca nos contratos já gerados (de qualquer advogado); traz só a qualificação.
function ClienteRecorrente({ onEscolher }: { onEscolher: (s: SugestaoCliente) => void }) {
  const [q, setQ] = useState("");
  const [lista, setLista] = useState<SugestaoCliente[]>([]);
  const [aberto, setAberto] = useState(false);

  useEffect(() => {
    const termo = q.trim();
    if (termo.length < 3) {
      setLista([]);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      sugerirClientes(termo, ctrl.signal)
        .then((r) => !ctrl.signal.aborted && setLista(r.sugestoes))
        .catch(() => !ctrl.signal.aborted && setLista([]));
    }, 300);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [q]);

  return (
    <div className="relative mb-4">
      <label className="block text-sm font-semibold text-foreground mb-1">
        Cliente já atendido?
      </label>
      <Input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => setAberto(true)}
        onBlur={() => setTimeout(() => setAberto(false), 150)}
        placeholder="Busque por nome, CPF ou CNPJ (mín. 3 caracteres)"
      />
      {aberto && lista.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-border bg-card shadow-lg text-sm">
          {lista.map((s) => (
            <li
              key={s.documento}
              onMouseDown={(e) => {
                e.preventDefault();
                onEscolher(s);
                setQ("");
                setLista([]);
                setAberto(false);
              }}
              className="px-3 py-2 cursor-pointer hover:bg-primary/10"
            >
              {s.nome}
              <span className="text-muted"> · {formatDoc(s.documento)} · dados de {dataBR(s.data_contrato)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PJForm({
  data,
  loadingCNPJ,
  loaded,
  editavel,
  receita,
  onUpdate,
  onCNPJLookup,
}: {
  data: ContratantePJ;
  loadingCNPJ: boolean;
  loaded: boolean;
  editavel: boolean;
  receita?: { situacao: string; socios: SocioReceita[] };
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
            value={formatarCNPJ(data.cnpj)}
            onChange={(e) => onUpdate({ cnpj: limparCNPJ(e.target.value) })}
            placeholder="00.000.000/0000-00 ou 12.ABC.345/01DE-35"
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

      <FormField label="WhatsApp" hint="Opcional. Para enviar o link de assinatura pelo WhatsApp">
        <Input
          type="tel"
          value={data.whatsapp || ""}
          onChange={(e) => onUpdate({ whatsapp: formatTelefone(e.target.value) })}
          placeholder="(31) 99999-9999"
        />
      </FormField>

      {receita?.situacao && receita.situacao.toUpperCase() !== "ATIVA" && (
        <p className="md:col-span-2 text-sm rounded-lg border border-warning/30 bg-warning/10 text-warning px-3 py-2">
          Situação cadastral na Receita: <strong>{receita.situacao}</strong>. Confirme com o
          cliente antes de seguir com o contrato.
        </p>
      )}

      {loaded && (
        <FormField label="Razão Social" required>
          <Input
            value={data.razao_social}
            onChange={(e) => onUpdate({ razao_social: e.target.value })}
            readOnly={!editavel}
            placeholder={editavel ? "Digite a razão social" : "Preenchido automaticamente pelo CNPJ"}
            className={editavel ? "" : "bg-border/35 border-muted text-muted cursor-not-allowed"}
          />
        </FormField>
      )}

      {loaded && (
        <FormField label="Endereço" required>
          <Input
            value={data.endereco}
            onChange={(e) => onUpdate({ endereco: e.target.value })}
            readOnly={!editavel}
            placeholder={editavel ? "Rua, n. 0, bairro, cidade/UF, CEP 00000-000" : "Preenchido automaticamente pelo CNPJ"}
            className={editavel ? "" : "bg-border/35 border-muted text-muted cursor-not-allowed"}
          />
        </FormField>
      )}

      <div className="md:col-span-2">
        <RepresentantesForm
          representantes={reps}
          socios={receita?.socios ?? []}
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
  socios,
  onChange,
}: {
  representantes: RepresentantePJ[];
  socios: SocioReceita[];
  onChange: (reps: RepresentantePJ[]) => void;
}) {
  const update = (i: number, partial: Partial<RepresentantePJ>) =>
    onChange(representantes.map((r, idx) => (idx === i ? { ...r, ...partial } : r)));

  const jaUsados = new Set(representantes.map((r) => r.nome.trim().toLowerCase()));
  const sugestoes = socios.filter((s) => !jaUsados.has(s.nome.trim().toLowerCase()));
  // Só preenche o nome, e só no clique: o QSA não prova poder de representação.
  const preencher = (nome: string) => {
    const vazio = representantes.findIndex((r) => !r.nome.trim());
    if (vazio >= 0) update(vazio, { nome });
    else onChange([...representantes, { ...emptyRepresentante(), nome }]);
  };

  return (
    <>
      <Checkbox
        label="Adicionar dados do(s) representante(s) legal(is)"
        checked={representantes.length > 0}
        onChange={(checked) => onChange(checked ? [emptyRepresentante()] : [])}
      />

      {sugestoes.length > 0 && (
        <div className="mt-3">
          <p className="text-xs text-muted mb-2">
            Sócios na Receita (QSA). Confira o contrato social: ser sócio-administrador não
            garante poder de assinar sozinho.
          </p>
          <div className="flex flex-wrap gap-2">
            {sugestoes.map((s) => (
              <button
                key={s.nome}
                type="button"
                onClick={() => preencher(s.nome)}
                className="px-3 py-1 rounded-full border border-primary-light text-primary text-xs font-medium hover:bg-primary-light/20 transition"
              >
                Preencher: {s.nome}
                {s.qualificacao && ` (${s.qualificacao})`}
              </button>
            ))}
          </div>
        </div>
      )}

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
            <FormField label="WhatsApp do Representante" hint="Opcional">
              <Input
                type="tel"
                value={rep.whatsapp || ""}
                onChange={(e) => update(i, { whatsapp: formatTelefone(e.target.value) })}
                placeholder="(31) 99999-9999"
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
        setCepData(null);
        setCepError("CEP não encontrado. Digite o endereço completo abaixo.");
        return;
      }
      const cData = { logradouro: result.logradouro, bairro: result.bairro, localidade: result.localidade, uf: result.uf };
      setCepData(cData);
      buildEndereco(cData, numero, complemento, formatCEP(digits));
    } catch {
      setCepData(null);
      setCepError("Erro ao buscar CEP. Digite o endereço completo abaixo.");
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

  // CEP que falhou (não achado, ViaCEP fora) libera a digitação do endereço inteiro.
  const enderecoRevelado = cepData != null || cepError != null || (data.endereco?.trim().length ?? 0) > 0;
  // Montado do CEP nesta sessão: trava, senão número/complemento sobrescreveriam a digitação.
  const enderecoEditavel = cepData == null;

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

      <FormField label="WhatsApp" hint="Opcional. Para enviar o link de assinatura pelo WhatsApp">
        <Input
          type="tel"
          value={data.whatsapp || ""}
          onChange={(e) => onUpdate({ whatsapp: formatTelefone(e.target.value) })}
          placeholder="(31) 99999-9999"
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
            onChange={(e) => onUpdate({ endereco: e.target.value })}
            readOnly={!enderecoEditavel}
            placeholder={enderecoEditavel ? "Rua, n. 0, bairro, cidade/UF, CEP 00000-000" : "Preenchido automaticamente pelo CEP"}
            className={enderecoEditavel ? "" : "bg-border/35 border-muted text-muted cursor-not-allowed"}
            required
          />
        </FormField>
      )}
    </div>
  );
}
