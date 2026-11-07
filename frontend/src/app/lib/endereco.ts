// Endereço do contratante PF: o contrato guarda UMA string; CEP, número e complemento são
// campos de tela remontados dela ao reabrir (ver GLOSSARY.md: Dados de tela).

export interface ViaCep {
  logradouro: string;
  bairro: string;
  localidade: string;
  uf: string;
}

/** Busca o CEP no ViaCEP — o único lugar do front que fala com ele.
 * Devolve null quando o CEP não existe (ou não tem 8 dígitos) e lança em falha de rede/serviço;
 * campos que o ViaCEP não manda (CEP único de cidade pequena vem sem rua) chegam como "". */
export async function buscarCep(cep: string): Promise<ViaCep | null> {
  const d = cep.replace(/\D/g, "");
  if (d.length !== 8) return null;
  const res = await fetch(`https://viacep.com.br/ws/${d}/json/`);
  if (!res.ok) throw new Error(`ViaCEP respondeu ${res.status}`);
  const r = await res.json();
  if (r.erro) return null;
  return { logradouro: r.logradouro || "", bairro: r.bairro || "", localidade: r.localidade || "", uf: r.uf || "" };
}

export function formatCEP(digits: string): string {
  const d = digits.replace(/\D/g, "").slice(0, 8);
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d;
}

/** "<logradouro>[, n. X][, <comp>], <bairro>, <cidade>/<UF>, CEP 00000-000" */
export function montarEndereco(via: ViaCep, numero: string, complemento: string, cep: string): string {
  const num = numero ? `, n. ${numero}` : "";
  const comp = complemento ? `, ${complemento}` : "";
  return `${via.logradouro}${num}${comp}, ${via.bairro}, ${via.localidade}/${via.uf}, CEP ${formatCEP(cep)}`;
}

/** Inverso de montarEndereco: reidrata CEP/número/complemento ao editar. Texto livre devolve vazio. */
export function desmontarEndereco(endereco: string | undefined) {
  const vazio = { cep: "", numero: "", complemento: "" };
  const partes = (endereco || "").split(", ");
  const ultima = partes[partes.length - 1] || "";
  if (partes.length < 4 || !ultima.startsWith("CEP ")) return vazio;

  const meio = partes.slice(1, -3); // entre logradouro e bairro: número e/ou complemento
  return {
    cep: formatCEP(ultima),
    numero: (meio.find((p) => p.startsWith("n. ")) || "").replace("n. ", ""),
    complemento: meio.filter((p) => !p.startsWith("n. ")).join(", "),
  };
}
