// Ciclo de vida do Rascunho (GLOSSARY.md): retomar e apagar passam por aqui, com um Armazem
// no lugar do servidor e da cópia local — os testes usam um em memória. Sem React, sem rede.
// As regras de apagar (gerar, descartar, rascunho antigo) vivem só em apagarRascunho.

export interface CopiaRascunho {
  dados: Record<string, unknown>;
  passo: number;
  atualizadoEm: number; // ms; o adapter converte o horário da API
  versao: string | null; // updated_at do servidor, base da concorrência otimista do autosave
}

export interface Armazem {
  /** Rejeita se o servidor não tem o rascunho. */
  lerServidor(id: string): Promise<CopiaRascunho>;
  lerLocal(id: string): CopiaRascunho | null;
  apagarServidor(id: string): Promise<void>;
  apagarLocal(id: string): void;
}

export const ULTIMA_ETAPA = 7;

/** Retoma na etapa exata em que parou, até a última. */
export function passoDeRetomada(passo: number): number {
  return Number.isFinite(passo) ? Math.min(Math.max(Math.trunc(passo), 1), ULTIMA_ETAPA) : 1;
}

export interface Retomada {
  dados: Record<string, unknown>;
  passo: number;
  versaoServidor: string | null;
}

/**
 * A cópia local mais nova que a do servidor significa que o último salvamento falhou: vence, mas
 * a versão base continua a do servidor. Sem servidor, só a cópia local; sem nenhuma, null.
 */
export async function retomarRascunho(id: string, arm: Armazem): Promise<Retomada | null> {
  const local = arm.lerLocal(id);
  let servidor: CopiaRascunho | null = null;
  try {
    servidor = await arm.lerServidor(id);
  } catch {
    servidor = null;
  }
  const escolhida = local && (!servidor || local.atualizadoEm > servidor.atualizadoEm) ? local : servidor;
  if (!escolhida) return null;
  return { dados: escolhida.dados, passo: passoDeRetomada(escolhida.passo), versaoServidor: servidor?.versao ?? null };
}

/** Apaga servidor e cópia local juntos. Falha do servidor não impede limpar o local. */
export async function apagarRascunho(id: string, arm: Armazem): Promise<void> {
  arm.apagarLocal(id);
  await arm.apagarServidor(id).catch(() => undefined);
}
