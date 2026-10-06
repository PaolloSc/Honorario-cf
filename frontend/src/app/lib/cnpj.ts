// CNPJ alfanumérico (Receita, a partir de jul/2026): as 12 primeiras posições são
// 0-9 ou A-Z maiúsculas; os 2 dígitos verificadores continuam numéricos. Os CNPJs
// só com números seguem válidos com o mesmo cálculo.
// Fonte: Receita Federal, "Perguntas e respostas — CNPJ alfanumérico", pergunta 14.

/** Só 0-9/A-Z, em maiúsculas, no máximo 14 posições. */
export function limparCNPJ(valor: string): string {
  return (valor || "").toUpperCase().replace(/[^0-9A-Z]/g, "").slice(0, 14);
}

/** 12.ABC.345/01DE-35 — aceita o valor com ou sem máscara. */
export function formatarCNPJ(valor: string): string {
  return limparCNPJ(valor)
    .replace(/^(\w{2})(\w)/, "$1.$2")
    .replace(/^(\w{2}\.\w{3})(\w)/, "$1.$2")
    .replace(/^(\w{2}\.\w{3}\.\w{3})(\w)/, "$1/$2")
    .replace(/^(\w{2}\.\w{3}\.\w{3}\/\w{4})(\w)/, "$1-$2");
}

// Módulo 11 com o valor de cada caractere = código ASCII − 48 ("0"=0 … "9"=9, "A"=17 … "Z"=42).
function digitoVerificador(base: string): number {
  let soma = 0;
  let peso = 2;
  for (let i = base.length - 1; i >= 0; i--) {
    soma += (base.charCodeAt(i) - 48) * peso;
    peso = peso === 9 ? 2 : peso + 1;
  }
  const resto = soma % 11;
  return resto < 2 ? 0 : 11 - resto;
}

export function cnpjValido(valor: string): boolean {
  const c = (valor || "").toUpperCase().replace(/[.\-/\s]/g, "");
  if (!/^[0-9A-Z]{12}\d{2}$/.test(c)) return false;
  if (/^(\d)\1{13}$/.test(c)) return false;
  const dv1 = digitoVerificador(c.slice(0, 12));
  const dv2 = digitoVerificador(c.slice(0, 12) + dv1);
  return c.endsWith(`${dv1}${dv2}`);
}
