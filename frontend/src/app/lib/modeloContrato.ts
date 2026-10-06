// "Usar como modelo": prepara o form_data de um contrato antigo para virar um contrato novo.
// cliente = mesmo cliente, novo escopo (zera escopos/honorários)
// escopo  = mesmo escopo, outro cliente (zera contratantes e contatos do cliente)
export type ModoModelo = "cliente" | "escopo";

// Datas de vencimento de contrato antigo quase sempre já passaram: nunca copiar.
const DATA_VENCIMENTO = /^(dia_)?vencimento\w*_data$/;

function semDatasDeVencimento(valor: unknown): unknown {
  if (Array.isArray(valor)) return valor.map(semDatasDeVencimento);
  if (!valor || typeof valor !== "object") return valor;
  return Object.fromEntries(
    Object.entries(valor)
      .filter(([chave]) => !DATA_VENCIMENTO.test(chave))
      .map(([chave, v]) => [chave, semDatasDeVencimento(v)])
  );
}

export function prepararModelo(dados: Record<string, unknown>, modo: ModoModelo): Record<string, unknown> {
  const copia = semDatasDeVencimento(dados) as Record<string, unknown>;
  const participacao = { ...((copia.participacao as Record<string, unknown>) ?? {}) };
  if (modo === "cliente") {
    copia.escopos = [];
    // a base da participação aponta para um escopo/honorário que não existe mais
    delete participacao.base_tipo;
    delete participacao.base_escopo_index;
    delete participacao.base_honorario;
    delete participacao.base_label;
  } else {
    copia.contratantes = [];
    copia.incluir_partes_relacionadas = false;
    delete copia.email_destinatario;
    participacao.contato_financeiro_nome = "";
    participacao.contato_financeiro_email = "";
    participacao.contato_financeiro_telefone = "";
    participacao.categoria_cliente = "";
    participacao.etiquetas = [];
    participacao.listas_transmissao = [];
  }
  copia.participacao = participacao;
  return copia;
}
