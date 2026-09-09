// Contrato de consumidor / transporte aereo. Espelha
// backend/app/models/contrato_consumidor.py.

export const TIPO_CONSUMIDOR_AEREO = "consumidor_aereo";

// Valor do milheiro (1.000 milhas) por companhia — tabela fixa do escritorio.
export const MILHEIRO_POR_COMPANHIA: Record<string, number> = {
  Gol: 40,
  Latam: 40,
  Azul: 40,
  Aeroméxico: 60,
  Avianca: 60,
  "American Airlines": 80,
  "United Airlines": 80,
  "Delta Air Lines": 80,
  "Air Canada": 80,
  "Iberia L.A.E": 80,
  "Air France": 80,
  Lufthansa: 80,
  "British Airways": 80,
  TAP: 80,
  KLM: 80,
  Emirates: 100,
  "Qatar Airways": 100,
  "Japan Airlines": 100,
};

// Apelidos que aparecem na razao social da Receita mas nao batem com o nome da
// tabela do milheiro (ex.: "TAM LINHAS AEREAS S.A." é a Latam).
const APELIDOS: Record<string, string> = {
  TAM: "Latam",
  IBERIA: "Iberia L.A.E",
  UNITED: "United Airlines",
  DELTA: "Delta Air Lines",
  AMERICAN: "American Airlines",
  QATAR: "Qatar Airways",
  AEROMEXICO: "Aeroméxico",
};

function semAcento(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();
}

// Palavra inteira: evita casar "TAP" dentro de "ETAPA".
function contemTermo(alvo: string, termo: string): boolean {
  const escapado = semAcento(termo).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^A-Z0-9])${escapado}([^A-Z0-9]|$)`).test(alvo);
}

/** Identifica a companhia a partir da razão social devolvida pela consulta de CNPJ. */
export function detectarCompanhia(razaoSocial: string): string | null {
  const alvo = semAcento(razaoSocial);
  if (!alvo.trim()) return null;

  // Nome mais longo primeiro: "American Airlines" antes de "Air Canada".
  const daTabela = Object.keys(MILHEIRO_POR_COMPANHIA)
    .sort((a, b) => b.length - a.length)
    .find((nome) => contemTermo(alvo, nome));
  if (daTabela) return daTabela;

  const apelido = Object.keys(APELIDOS).find((a) => contemTermo(alvo, a));
  return apelido ? APELIDOS[apelido] : null;
}

export interface ContratanteConsumidorPF {
  tipo: "PF";
  nome: string;
  genero: "F" | "M";
  nacionalidade: string;
  cpf: string;
  rg?: string;
  // endereco e' montado a partir dos campos abaixo — o usuario nao digita direto.
  endereco: string;
  cep?: string;
  logradouro?: string;
  bairro?: string;
  cidade?: string;
  uf?: string;
  numero?: string;
  complemento?: string;
  email?: string;
  celular?: string;
}

export interface ContratanteConsumidorPJ {
  tipo: "PJ";
  razao_social: string;
  cnpj: string;
  endereco: string;
  email?: string;
  representante_nome: string;
  representante_cpf: string;
  representante_genero: "F" | "M";
  representante_nacionalidade: string;
  representante_email?: string;
}

export type ContratanteConsumidor = ContratanteConsumidorPF | ContratanteConsumidorPJ;

export function nomeExibicao(c: ContratanteConsumidor): string {
  return c.tipo === "PJ" ? c.razao_social : c.nome;
}

// Quem recebe o contrato e assina: na PJ, o representante legal.
export function emailContato(c: ContratanteConsumidor): string {
  if (c.tipo === "PJ") return c.representante_email || c.email || "";
  return c.email || "";
}

export function nomeSignatario(c: ContratanteConsumidor): string {
  return c.tipo === "PJ" ? c.representante_nome : c.nome;
}

export interface ReAerea {
  companhia: string;
  razao_social: string;
  cnpj: string;
  valor_milheiro_override?: number;
}

export function reVazia(): ReAerea {
  return { companhia: "", razao_social: "", cnpj: "" };
}

export function valorMilheiro(re: ReAerea): number | undefined {
  return re.valor_milheiro_override ?? MILHEIRO_POR_COMPANHIA[re.companhia];
}

export interface ConsumidorFormData {
  tipo_contrato: typeof TIPO_CONSUMIDOR_AEREO;
  contratantes: ContratanteConsumidor[];
  res: ReAerea[];
  juizado: string;
  prazo_pagamento_dias: number;
  elabora_reclamacao: boolean;
  data_contrato?: string;
  comarca: string;
  email_destinatario?: string;
}

// Rotulo generico, igual ao contrato de honorarios. O gerador resolve a
// concordancia (brasileira/brasileiro) pelo genero do contratante.
export const NACIONALIDADE_PADRAO = "Brasileira (o)";

export function contratantePJVazio(): ContratanteConsumidorPJ {
  return {
    tipo: "PJ",
    razao_social: "",
    cnpj: "",
    endereco: "",
    email: "",
    representante_nome: "",
    representante_cpf: "",
    representante_genero: "F",
    representante_nacionalidade: NACIONALIDADE_PADRAO,
    representante_email: "",
  };
}

export function contratanteVazio(): ContratanteConsumidorPF {
  return {
    tipo: "PF",
    nome: "",
    genero: "F",
    nacionalidade: NACIONALIDADE_PADRAO,
    cpf: "",
    rg: "",
    endereco: "",
    cep: "",
    logradouro: "",
    bairro: "",
    cidade: "",
    uf: "",
    numero: "",
    complemento: "",
    email: "",
    celular: "",
  };
}


export function formVazio(): ConsumidorFormData {
  return {
    tipo_contrato: TIPO_CONSUMIDOR_AEREO,
    contratantes: [contratanteVazio()],
    res: [reVazia()],
    juizado: "Juizado Especial Cível de Belo Horizonte - MG",
    prazo_pagamento_dias: 10,
    elabora_reclamacao: true,
    comarca: "Belo Horizonte",
  };
}
