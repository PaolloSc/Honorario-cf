function resolveApiBase(): string {
  // 1. Vercel environment variable takes priority
  const envBase = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  if (envBase) return envBase;

  // 2. In browser (production), use same domain — Railway typically runs on same domain via proxy
  if (typeof window !== "undefined") {
    const protocol = window.location.protocol;
    const host = window.location.hostname;
    // Vercel serverless functions are at /api on the same domain
    return `${protocol}//${host}`;
  }

  // 3. Development fallback
  return "http://127.0.0.1:8000";
}

const API_BASE = resolveApiBase();

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  let res: Response;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 12000);

  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: options?.signal || controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`Tempo esgotado ao conectar na API (${API_BASE}).`);
    }
    const detail = err instanceof Error ? err.message : "erro desconhecido";
    throw new Error(`Falha ao conectar na API (${API_BASE}): ${detail}`);
  } finally {
    clearTimeout(timeoutId);
  }

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }

  return res.json();
}

export async function generateContract(data: unknown) {
  return request<{
    success: boolean;
    message: string;
    contract_id?: string;
    download_url?: string;
  }>("/api/contract/generate", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function downloadContract(contractId: string) {
  const res = await fetch(
    `${API_BASE}/api/contract/${contractId}/download`
  );
  if (!res.ok) throw new Error("Failed to download contract");
  return res.blob();
}

export async function sendEmail(data: {
  contract_id: string;
  destinatario_email: string;
  destinatario_nome: string;
  assunto?: string;
}) {
  return request<{ success: boolean; message: string }>("/api/email/send", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function sendForSignature(data: {
  contract_id: string;
  signatarios: Array<{ email: string; name: string; role: string }>;
}) {
  return request<{ success: boolean; message: string }>(
    "/api/docuseal/send-for-signature",
    {
      method: "POST",
      body: JSON.stringify(data),
    }
  );
}

export async function lookupCNPJ(cnpj: string) {
  const cnpjClean = cnpj.replace(/\D/g, "");
  return request<{
    cnpj: string;
    razao_social: string;
    nome_fantasia: string;
    endereco: string;
    situacao_cadastral: string;
  }>(`/api/cnpj/${cnpjClean}`);
}
