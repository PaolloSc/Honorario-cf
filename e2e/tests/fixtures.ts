import { test as base, expect, request, type APIRequestContext, type Page } from "@playwright/test";
import { BACK, FRONT } from "../playwright.config";

/** Marca todo dado criado pelos testes; a limpeza (e2e/README.md) apaga so o que tem esta marca. */
export const MARCA = "[TESTE-QA-DELETAR]";

const TOKEN = process.env.E2E_TOKEN ?? "";

// Producao e' proibida: so homolog (URL com "homolog") ou localhost.
if (!FRONT || !BACK) throw new Error("Defina E2E_FRONT e E2E_BACK (URLs do homolog ou do ambiente local).");
if (!/homolog|localhost|127\.0\.0\.1/.test(FRONT) || !/homolog|localhost|127\.0\.0\.1/.test(BACK)) {
  throw new Error("E2E so roda em homolog ou local; recusando alvo: " + new URL(FRONT).host);
}

export function exigirToken() {
  if (!TOKEN) throw new Error("Defina E2E_TOKEN no ambiente (nao fica no repo).");
}

/** Entra pelo link de convidado (sessao de admin do ambiente de teste). */
export async function entrar(page: Page) {
  exigirToken();
  for (let tentativa = 0; tentativa < 3; tentativa++) { // corrida do cookie de CSRF na 1a visita (#902647c)
    await page.goto(`/convite/${TOKEN}`);
    try {
      await page.waitForURL((u) => !u.pathname.startsWith("/convite"), { timeout: 20_000 });
      return;
    } catch { /* tenta de novo */ }
  }
  throw new Error("convite nao entrou apos 3 tentativas");
}

export async function api(): Promise<APIRequestContext> {
  exigirToken();
  return request.newContext({ baseURL: BACK, extraHTTPHeaders: { Authorization: `Bearer ${TOKEN}` } });
}

const PF = (nome: string) => ({
  tipo: "PF", nome, nacionalidade: "brasileira", cpf: "123.456.789-09", profissao: "engenheira",
  estado_civil: "Casado(a)", endereco: "Rua das Flores, 100, Belo Horizonte/MG, CEP 30.100-000", email: "qa@exemplo.com",
});

/** Contrato de origem criado pela API (ficticio, marcado) para os documentos derivados (distrato etc.). */
export async function criarContratoOrigem(a: APIRequestContext, sufixo: string) {
  const nome = `${MARCA} Maria ${sufixo}`;
  const r = await a.post("/api/contract/generate", {
    data: {
      contratantes: [PF(nome)], incluir_partes_relacionadas: false,
      escopos: [{ tipo: "consultoria_contratual", honorarios: ["mensalidade"],
        mensalidade: { valor: 2500, subtipo: "advocacia_partido", dia_vencimento: "10", variacao_preco: "sem_variacao" } }],
      acessorios: { tem_reembolso: false, reembolso_limitado: false, tem_penalidade_inadimplemento: false },
      participacao: { tem_participacao: false },
    },
  });
  expect(r.status(), await r.text()).toBe(200);
  const j = await r.json();
  return { id: (j.contract_id ?? j.id) as string, nome };
}

export const test = base;
export { expect };
