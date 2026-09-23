// Datas vindas da API, sempre mostradas no horário de Brasília.
//
// O backend grava em UTC, mas o banco guarda o timestamp sem fuso e a API o
// devolve sem o "Z" ("2026-09-23T18:23:16"). O navegador lia isso como hora
// local e mostrava 3 horas a mais. Todo timestamp da API passa por aqui.

const FUSO = "America/Sao_Paulo";

export function dataDaApi(valor: string): Date {
  if (!valor.includes("T")) return new Date(`${valor}T12:00:00Z`); // só a data: meio-dia evita virar o dia
  return new Date(/([zZ]|[+-]\d{2}:?\d{2})$/.test(valor) ? valor : `${valor}Z`);
}

export function formatarDataHora(valor: string): string {
  return dataDaApi(valor).toLocaleString("pt-BR", {
    timeZone: FUSO,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatarData(valor: string): string {
  return dataDaApi(valor).toLocaleDateString("pt-BR", { timeZone: FUSO });
}

// "Hoje" em Brasília no formato AAAA-MM-DD. toISOString() dá o dia em UTC,
// que depois das 21h já é amanhã.
export function hojeBrasilia(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: FUSO }).format(new Date());
}
