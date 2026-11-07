// Cliente HTTP único do front: uma base de URL, um token (renovado na hora), um formato de erro.
// Todas as chamadas à API passam por aqui (api.ts, emissao-api, finance-api, nfse-api e páginas).
// Sem import de valor: roda no node para o http.check.ts.

function resolveApiBase(): string {
  // 1. Variável da Vercel tem prioridade
  const envBase = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  if (envBase) return envBase;

  // 2. No navegador: mesmo domínio (funções da Vercel em /api)
  if (typeof window !== "undefined") {
    const protocol = window.location.protocol;
    const host = window.location.hostname;
    // Dev local: backend separado em :8000
    if (host === "localhost" || host === "127.0.0.1") {
      return `${protocol}//${host}:8000`;
    }
    return `${protocol}//${host}`;
  }

  // 3. Fallback de desenvolvimento
  return "http://127.0.0.1:8000";
}

export const API_BASE = resolveApiBase();

let _accessToken: string | null = null;
let _expiresAt: number | null = null; // epoch em segundos, lido do proprio JWT

/** `exp` do JWT sem validar assinatura — so' para saber quando renovar. */
function expDoJwt(jwtToken: string): number | null {
  const payload = jwtToken.split(".")[1];
  if (!payload) return null;
  try {
    // base64url vem sem padding, e o id_token traz `name` acentuado: sem repor
    // o "=" e sem decodificar UTF-8, o parse falha e a renovacao proativa some.
    const b64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const bin = atob(b64.padEnd(Math.ceil(b64.length / 4) * 4, "="));
    const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
    const exp = JSON.parse(new TextDecoder().decode(bytes))?.exp;
    return typeof exp === "number" ? exp : null;
  } catch {
    return null;
  }
}

export function setAccessToken(token: string | null) {
  _accessToken = token;
  _expiresAt = token ? expDoJwt(token) : null;
}

/** Token ausente ou a menos de 60s de vencer (margem pro tempo de rede). */
function tokenVencido(): boolean {
  if (!_accessToken) return true;
  if (_expiresAt === null) return false; // sem exp legivel: deixa o backend julgar
  return Date.now() >= _expiresAt * 1000 - 60_000;
}

/**
 * Puxa a sessao do next-auth, o que dispara o callback `jwt` no servidor e
 * renova o id_token junto ao Azure. O `refetchInterval` do SessionProvider so'
 * roda com a aba viva e em foco — depois de uma reuniao, de o notebook dormir ou
 * de a aba ficar horas no fundo, o token em memoria ja' venceu e a API responde
 * 401 "Token expirado". Aqui a renovacao acontece na hora da chamada.
 */
async function renovarToken(): Promise<void> {
  if (typeof window === "undefined") return;
  try {
    const { getSession } = await import("next-auth/react");
    const session = await getSession();
    setAccessToken(session?.accessToken || null);
  } catch (e) {
    console.error("[AUTH] Falha ao renovar a sessao:", e);
  }
}

/**
 * Erro da API: a resposta chegou com status de erro. `corpo` é o texto cru da resposta;
 * a mensagem segue sempre o formato "API error NNN: corpo" (erro422/emissao/documentos leem assim).
 */
export class ErroApi extends Error {
  readonly status: number;
  readonly corpo: string;

  constructor(status: number, corpo: string) {
    super(`API error ${status}: ${corpo}`);
    this.name = "ErroApi";
    this.status = status;
    this.corpo = corpo;
  }
}

/** 409: outra aba/computador gravou antes (ex.: rascunho com `known_updated_at` velho). */
export class ConflitoError extends ErroApi {
  constructor(corpo: string) {
    super(409, corpo);
    this.name = "ConflitoError";
  }
}

/**
 * 401 que sobreviveu a uma renovacao. Nem todo 401 e' expiracao — o backend
 * tambem recusa por audience errada, issuer divergente ou token sem e-mail.
 * Chamar tudo de "sessao expirada" mandava o usuario relogar a toa; o motivo
 * real vai junto para o erro dizer a verdade.
 */
export class SessaoExpiradaError extends Error {
  readonly motivo: string;

  constructor(motivo?: string) {
    const expirou = !motivo || /expirado/i.test(motivo);
    super(
      expirou
        ? "Sua sessão expirou. Faça login novamente para continuar."
        : `A API recusou o acesso: ${motivo}`,
    );
    this.name = "SessaoExpiradaError";
    this.motivo = motivo ?? "";
  }
}

/** `detail` do FastAPI, quando houver; senao o corpo cru. */
async function motivoDaResposta(res: Response): Promise<string> {
  try {
    const texto = await res.clone().text();
    try {
      const json = JSON.parse(texto);
      const detail = json?.detail;
      if (typeof detail === "string") return detail;
    } catch {
      // corpo nao e' JSON — devolve como veio
    }
    return texto.slice(0, 200);
  } catch {
    return "";
  }
}

function modoDev(): boolean {
  return (
    typeof window !== "undefined" &&
    process.env.NEXT_PUBLIC_DEV_MODE === "true" &&
    !!localStorage.getItem("dev_user_email")
  );
}

function getDevHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  if (process.env.NEXT_PUBLIC_DEV_MODE !== "true") return {};
  const email = localStorage.getItem("dev_user_email");
  const role = localStorage.getItem("dev_user_role");
  const name = localStorage.getItem("dev_user_name");
  if (!email) return {};
  const h: Record<string, string> = { "X-Dev-User-Email": email };
  if (role) h["X-Dev-User-Role"] = role;
  if (name) h["X-Dev-User-Name"] = name;
  return h;
}

export function getAuthHeaders(): Record<string, string> {
  const h: Record<string, string> = {};
  if (_accessToken) h["Authorization"] = `Bearer ${_accessToken}`;
  Object.assign(h, getDevHeaders());
  return h;
}

/** Renova o id_token se ele ja' venceu, antes de qualquer chamada a API. */
export async function garantirTokenValido(): Promise<void> {
  if (!modoDev() && tokenVencido()) {
    await renovarToken();
  }
}

/**
 * fetch autenticado com token sempre valido: renova antes de mandar se ja' venceu
 * e, se mesmo assim voltar 401, renova e tenta uma unica vez mais.
 */
export async function fetchAutenticado(
  url: string,
  init?: RequestInit,
): Promise<Response> {
  await garantirTokenValido();

  const montarHeaders = (): Record<string, string> => ({
    ...((init?.headers as Record<string, string>) || {}),
    ...getAuthHeaders(),
  });

  let res = await fetch(url, { ...init, headers: montarHeaders() });

  if (res.status === 401 && !modoDev()) {
    // O token pode ter vencido entre a montagem e a chegada do request, ou o
    // relogio do cliente estar adiantado. Renova uma vez e repete.
    const anterior = _accessToken;
    await renovarToken();
    if (!_accessToken) throw new SessaoExpiradaError(await motivoDaResposta(res));
    if (_accessToken !== anterior) {
      res = await fetch(url, { ...init, headers: montarHeaders() });
    }
    if (res.status === 401) throw new SessaoExpiradaError(await motivoDaResposta(res));
  }

  return res;
}

export interface OpcoesApi extends RequestInit {
  /** Aborta depois de N ms. Sem valor: sem limite (emissão de NFS-e e SEFIN podem demorar). */
  timeoutMs?: number;
}

/**
 * Chamada à API com a base única. Devolve a Response quando ok; senão lança ErroApi
 * (ConflitoError no 409). Falha de rede/timeout vira Error "Falha/Tempo esgotado ao conectar".
 * Content-Type JSON só quando o corpo é texto (FormData define o próprio boundary).
 */
export async function chamarApi(path: string, opcoes: OpcoesApi = {}): Promise<Response> {
  const { timeoutMs, ...init } = opcoes;
  // Renova antes de armar o timeout: a ida ate' o /api/auth/session nao pode
  // consumir o tempo reservado para a chamada da API.
  await garantirTokenValido();

  const controller = timeoutMs ? new AbortController() : null;
  const timeoutId = controller ? setTimeout(() => controller.abort(), timeoutMs) : undefined;
  const headers: Record<string, string> = {
    ...(typeof init.body === "string" ? { "Content-Type": "application/json" } : {}),
    ...((init.headers as Record<string, string>) || {}),
  };

  let res: Response;
  try {
    res = await fetchAutenticado(`${API_BASE}${path}`, {
      ...init,
      signal: init.signal || controller?.signal,
      headers,
    });
  } catch (err) {
    if (err instanceof SessaoExpiradaError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      // Abortado por quem chamou (ex.: prévia substituída): repassa como veio.
      if (!controller?.signal.aborted) throw err;
      throw new Error(`Tempo esgotado ao conectar na API (${API_BASE}).`);
    }
    const detail = err instanceof Error ? err.message : "erro desconhecido";
    throw new Error(`Falha ao conectar na API (${API_BASE}): ${detail}`);
  } finally {
    clearTimeout(timeoutId);
  }

  if (!res.ok) {
    const corpo = await res.text();
    if (res.status === 409) throw new ConflitoError(corpo);
    throw new ErroApi(res.status, corpo);
  }
  return res;
}

/** chamarApi + JSON da resposta (204 => undefined). */
export async function chamarApiJson<T>(path: string, opcoes?: OpcoesApi): Promise<T> {
  const res = await chamarApi(path, opcoes);
  return res.status === 204 ? (undefined as T) : res.json();
}

/** `detail` em texto do corpo de um ErroApi, quando houver; null se não há. */
export function detalheDoErro(erro: unknown): string | null {
  if (!(erro instanceof ErroApi)) return null;
  try {
    const detail = JSON.parse(erro.corpo)?.detail;
    return typeof detail === "string" ? detail : null;
  } catch {
    return null;
  }
}
