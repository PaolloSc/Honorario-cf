// Cópia local do rascunho do wizard — só um buffer para quando o servidor não
// responde (rede caiu, sessão expirou). Assim que o servidor confirma, a cópia
// some: o formulário tem CPF/endereço de cliente e não deve ficar largado num
// navegador compartilhado.

const PREFIXO = "cf:rascunho:";

export interface RascunhoLocal {
  draft_id: string;
  form_data: Record<string, unknown>;
  current_step: number;
  client_name: string;
  updated_at: string; // ISO com "Z"
}

function nomeCliente(formData: Record<string, unknown>): string {
  const lista = formData.contratantes;
  const primeiro = Array.isArray(lista) ? (lista[0] as Record<string, unknown> | undefined) : undefined;
  return String(primeiro?.nome || primeiro?.razao_social || "").trim();
}

export function gravarLocal(draftId: string, formData: Record<string, unknown>, step: number) {
  try {
    const r: RascunhoLocal = {
      draft_id: draftId,
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

export function lerLocal(draftId: string): RascunhoLocal | null {
  try {
    const raw = localStorage.getItem(PREFIXO + draftId);
    return raw ? (JSON.parse(raw) as RascunhoLocal) : null;
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

export function listarLocais(): RascunhoLocal[] {
  const out: RascunhoLocal[] = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const chave = localStorage.key(i);
      if (!chave?.startsWith(PREFIXO)) continue;
      const r = lerLocal(chave.slice(PREFIXO.length));
      if (r) out.push(r);
    }
  } catch {
    return [];
  }
  return out.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}
