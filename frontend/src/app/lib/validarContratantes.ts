// Validacao do passo 1 (contratantes), pura, para rodar no node: ver validarContratantes.check.ts.
// cnpjValido vem de cnpj.ts (injetado para este arquivo rodar no node sem extensao de import).
interface Rep { nome?: string; cpf?: string; email?: string }
interface Contratante {
  tipo: "PF" | "PJ"; nome?: string; cpf?: string; estado_civil?: string; email?: string; endereco?: string;
  cnpj?: string; razao_social?: string; representantes?: Rep[];
}

export function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function isEmail(value: string | undefined): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text(value));
}

function isValidCPF(cpf: string): boolean {
  const d = cpf.replace(/\D/g, "");
  if (d.length !== 11) return false;
  // Reject known invalid patterns (all same digit)
  if (/^(\d)\1{10}$/.test(d)) return false;
  // First check digit
  let sum = 0;
  for (let i = 0; i < 9; i++) sum += parseInt(d[i]) * (10 - i);
  let check = 11 - (sum % 11);
  if (check >= 10) check = 0;
  if (parseInt(d[9]) !== check) return false;
  // Second check digit
  sum = 0;
  for (let i = 0; i < 10; i++) sum += parseInt(d[i]) * (11 - i);
  check = 11 - (sum % 11);
  if (check >= 10) check = 0;
  if (parseInt(d[10]) !== check) return false;
  return true;
}

/** A consulta de CNPJ trouxe razão social E endereço? Se não, os campos continuam editáveis. */
export function consultaCompleta(d: { razao_social?: string; endereco?: string }): boolean {
  return !!text(d.razao_social) && !!text(d.endereco);
}

export function validarContratantes(data: { contratantes: Contratante[] }, cnpjValido: (c: string) => boolean): string[] {
  const errors: string[] = [];

  if (data.contratantes.length === 0) {
    errors.push("Adicione pelo menos um contratante.");
    return errors;
  }

  data.contratantes.forEach((contratante, index) => {
    const label = `Contratante ${index + 1}`;

    if (contratante.tipo === "PF") {
      if (!text(contratante.nome)) errors.push(`${label}: informe o nome completo.`);
      if (!text(contratante.cpf)) errors.push(`${label}: informe o CPF.`);
      else if (!isValidCPF(contratante.cpf ?? "")) errors.push(`${label}: CPF inválido.`);
      if (!text(contratante.estado_civil)) errors.push(`${label}: informe o estado civil.`);
      if (!isEmail(contratante.email)) errors.push(`${label}: informe um e-mail válido.`);
      if (!text(contratante.endereco)) errors.push(`${label}: informe o endereço completo.`);
      return;
    }

    if (!cnpjValido(contratante.cnpj ?? "")) errors.push(`${label}: CNPJ inválido.`);
    if (!isEmail(contratante.email)) errors.push(`${label}: informe um e-mail válido.`);
    if (!text(contratante.razao_social)) errors.push(`${label}: busque o CNPJ ou informe a Razão Social.`);
    if (!text(contratante.endereco)) errors.push(`${label}: busque o CNPJ ou informe o endereço.`);
    // E-mail do representante é opcional: com e-mail ele assina; se nenhum tiver, assina o
    // e-mail da empresa (obrigatório acima). Preenchido, tem de ser válido.
    (contratante.representantes ?? []).forEach((rep, i) => {
      // Linha so com os padroes (nacionalidade/profissao) e' ignorada; com nome, CPF ou e-mail, vale o minimo.
      if (!text(rep.nome) && (text(rep.cpf) || text(rep.email))) {
        errors.push(`${label}: informe o nome do representante ${i + 1}.`);
      }
      if (text(rep.email) && !isEmail(rep.email)) {
        errors.push(`${label}: e-mail inválido do representante ${text(rep.nome) || i + 1}.`);
      }
      if (text(rep.cpf) && !isValidCPF(rep.cpf!)) {
        errors.push(`${label}: CPF inválido do representante ${text(rep.nome) || "sem nome"}.`);
      }
    });
  });

  return errors;
}

