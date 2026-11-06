// Conversão dos Dados do contrato para o formato atual (ticket 04). Lê do stdin
// [{ chave, dados }] e escreve [{ chave, dados }] no stdout. Usa a MESMA função que o wizard usa
// ao abrir (normalizarFormData), então o banco e a tela nunca divergem. Campos de topo que o wizard
// não conhece (ex.: contrato_origem_id) são preservados. Não toca em banco nem em rede.
//   node --experimental-strip-types scripts/converter-formato.ts < entrada.json > saida.json
import { readFileSync } from "node:fs";
import { normalizarFormData } from "../src/app/lib/estadoWizard.ts";

export function converter(dados: Record<string, unknown>): Record<string, unknown> {
  const novo = normalizarFormData(dados as never) as unknown as Record<string, unknown>;
  // JSON descarta undefined, como o banco faz; extras de topo sobrevivem
  return JSON.parse(JSON.stringify({ ...dados, ...novo }));
}

const entrada = JSON.parse(readFileSync(0, "utf-8")) as Array<{ chave: string; dados: Record<string, unknown> }>;
const saida = entrada.map(({ chave, dados }) => {
  const uma = converter(dados);
  const duas = converter(uma);
  if (JSON.stringify(uma) !== JSON.stringify(duas)) throw new Error(`não idempotente: ${chave}`);
  return { chave, dados: uma };
});
process.stdout.write(JSON.stringify(saida));
