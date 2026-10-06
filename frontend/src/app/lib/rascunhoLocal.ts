"use client";

// Cópia local do rascunho do wizard — só um buffer para quando o servidor não
// responde (rede caiu, sessão expirou). Assim que o servidor confirma, a cópia
// some: o formulário tem CPF/endereço de cliente e não deve ficar largado num
// navegador compartilhado. Por isso cada cópia leva o e-mail de quem a gravou,
// só aparece para essa pessoa, vence em 7 dias e é apagada no "Sair".

import { useSession } from "next-auth/react";

const PREFIXO = "cf:rascunho:";
const VALIDADE_MS = 7 * 24 * 60 * 60 * 1000;

export interface RascunhoLocal {
  draft_id: string;
  owner_email: string;
  form_data: Record<string, unknown>;
  current_step: number;
  client_name: string;
  updated_at: string; // ISO com "Z"
}

/** E-mail de quem está logado, normalizado; "" enquanto a sessão carrega. */
export function useDonoRascunho(): string {
  const { data } = useSession();
  let email = data?.user?.email || "";
  if (!email && process.env.NEXT_PUBLIC_DEV_MODE === "true" && typeof window !== "undefined") {
    try {
      email = localStorage.getItem("dev_user_email") || "";
    } catch {
      // sem localStorage, sem dono
    }
  }
  return email.trim().toLowerCase();
}

function nomeCliente(formData: Record<string, unknown>): string {
  const lista = formData.contratantes;
  const primeiro = Array.isArray(lista) ? (lista[0] as Record<string, unknown> | undefined) : undefined;
  return String(primeiro?.nome || primeiro?.razao_social || "").trim();
}

export function gravarLocal(draftId: string, formData: Record<string, unknown>, step: number, dono: string) {
  if (!dono) return; // sem dono não grava: ninguém conseguiria ler de volta
  try {
    const r: RascunhoLocal = {
      draft_id: draftId,
      owner_email: dono,
      form_data: formData,
      current_step: step,
      client_name: nomeCliente(formData),
      updated_at: new Date().toISOString(),
    };
    localStorage.setItem(PREFIXO + draftId, JSON.stringify(r));
  } catch {
    // quota cheia ou navegador em modo privado: o servidor continua sendo o salvamento
  }
}

/** Devolve a cópia só se for de `dono` e tiver menos de 7 dias (a vencida é apagada). */
export function lerLocal(draftId: string, dono: string): RascunhoLocal | null {
  try {
    const raw = localStorage.getItem(PREFIXO + draftId);
    if (!raw) return null;
    const r = JSON.parse(raw) as Partial<RascunhoLocal>;
    const idade = Date.now() - Date.parse(r.updated_at || "");
    if (!(idade < VALIDADE_MS)) {
      localStorage.removeItem(PREFIXO + draftId); // vencida ou ilegível
      return null;
    }
    // cópia de outra pessoa (ou antiga, sem dono) fica invisível até vencer
    if (!dono || r.owner_email !== dono) return null;
    return r as RascunhoLocal;
  } catch {
    return null;
  }
}

export function removerLocal(draftId: string) {
  try {
    localStorage.removeItem(PREFIXO + draftId);
  } catch {
    // sem localStorage, nada a limpar
  }
}

function chavesLocais(): string[] {
  const chaves: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const chave = localStorage.key(i);
    if (chave?.startsWith(PREFIXO)) chaves.push(chave);
  }
  return chaves;
}

export function listarLocais(dono: string): RascunhoLocal[] {
  const out: RascunhoLocal[] = [];
  try {
    for (const chave of chavesLocais()) {
      const r = lerLocal(chave.slice(PREFIXO.length), dono);
      if (r) out.push(r);
    }
  } catch {
    return [];
  }
  return out.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

/** Apaga todas as cópias locais deste navegador — chamado no "Sair". */
export function limparLocais() {
  try {
    for (const chave of chavesLocais()) localStorage.removeItem(chave);
  } catch {
    // sem localStorage, nada a limpar
  }
}
