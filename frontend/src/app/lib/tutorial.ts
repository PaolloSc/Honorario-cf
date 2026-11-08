// Textos do tutorial: o tour guiado de cada tela e a página "Como usar" leem daqui.

export type PassoTour = {
  titulo: string;
  texto: string;
  /** Elemento a destacar. Sem ele (ou se não estiver na tela), o balão aparece sem destaque. */
  alvo?: () => Element | null;
};

export type Tour = { chave: string; nome: string; passos: PassoTour[] };

/** Primeiro botão/link/menu visível cujo texto começa com `texto`. */
const botao = (texto: string) => () =>
  Array.from(document.querySelectorAll("button, a, summary")).find(
    (el) => el.textContent?.trim().startsWith(texto) && (el as HTMLElement).offsetParent !== null
  ) ?? null;
const sel = (css: string) => () => document.querySelector(css);
const visivel = (el: Element) => (el as HTMLElement).offsetParent !== null;
/** Campo do formulário pelo rótulo: o bloco do rótulo com o controle. */
const campo = (rotulo: string) => () => {
  const l = Array.from(document.querySelectorAll("main label")).find(
    (el) => el.textContent?.trim().startsWith(rotulo) && visivel(el)
  );
  return l ? l.parentElement : null;
};
/** Título de seção visível que começa com `texto`. */
const titulo = (texto: string) => () =>
  Array.from(document.querySelectorAll("main h2, main h3")).find(
    (el) => el.textContent?.trim().startsWith(texto) && visivel(el)
  ) ?? null;

// Etapa atual do assistente (1 a 7; 0 = fora dele). O ContractWizard marca; o tour lê.
let etapaAtual = 0;
const ouvintes = new Set<() => void>();
export function marcarEtapa(n: number) {
  etapaAtual = n;
  ouvintes.forEach((f) => f());
}
export function ouvirEtapa(f: () => void) {
  ouvintes.add(f);
  return () => {
    ouvintes.delete(f);
  };
}
export const lerEtapa = () => etapaAtual;

const ASSINATURA_X_EMAIL =
  "“Enviar para assinatura digital” manda o link do DocuSeal a cada signatário e bloqueia a edição. " +
  "“Enviar cópia para conferência” só manda o Word por e-mail para o cliente revisar; não é assinatura. " +
  "As duas pedem confirmação mostrando quem vai receber.";

export const TOURS: Tour[] = [
  {
    chave: "assistente-1",
    nome: "Novo contrato · etapa 1: Contratante",
    passos: [
      {
        titulo: "Contrato em 7 etapas",
        texto:
          "Preencha cada etapa e avance com “Próximo”. Tudo é salvo sozinho como rascunho: dá para sair e continuar depois. Em qualquer etapa, o botão ? explica a etapa aberta.",
      },
      {
        titulo: "Cliente já cadastrado?",
        texto: "Busque pelo nome ou CPF/CNPJ e os dados vêm preenchidos. Cliente novo: deixe em branco e preencha abaixo.",
        alvo: campo("Cliente já cadastrado"),
      },
      {
        titulo: "Pessoa física ou jurídica",
        texto: "Escolha antes de preencher: os campos mudam (CPF e estado civil, ou CNPJ, razão social e representante).",
        alvo: botao("Pessoa Física"),
      },
      {
        titulo: "Dados do contratante",
        texto: "Campos com * são obrigatórios. O e-mail recebe o contrato e o link de assinatura.",
        alvo: () => campo("Nome completo")() ?? campo("Razão Social")(),
      },
      {
        titulo: "Endereço",
        texto: "Digite o CEP para preencher rua, bairro e cidade; depois complete o número.",
        alvo: campo("CEP"),
      },
      {
        titulo: "Mais de um contratante",
        texto: "Use “+ Adicionar Contratante” para cada parte que assina junto.",
        alvo: botao("+ Adicionar Contratante"),
      },
    ],
  },
  {
    chave: "assistente-2",
    nome: "Novo contrato · etapa 2: Escopo",
    passos: [
      {
        titulo: "O que o escritório vai fazer",
        texto: "Marque um ou mais escopos. Cada um vira uma cláusula de objeto e tem seus próprios honorários na etapa 3.",
        alvo: titulo("2."),
      },
      {
        titulo: "Detalhes do escopo",
        texto: "Ao marcar, aparecem os campos daquele escopo (número dos autos, demandas, tema do parecer…). Preencha o que ele pedir.",
      },
      {
        titulo: "Outro escopo",
        texto: "O serviço não está na lista? Marque “Outro escopo (campo aberto)” e descreva com suas palavras.",
        alvo: campo("Outro escopo"),
      },
      {
        titulo: "Partes relacionadas",
        texto: "Marque se o contrato também vale para empresas e pessoas ligadas ao cliente (cláusula 2.4).",
        alvo: campo("Inserir Cláusula de Partes Relacionadas"),
      },
    ],
  },
  {
    chave: "assistente-3",
    nome: "Novo contrato · etapa 3: Honorários",
    passos: [
      {
        titulo: "Um bloco por escopo",
        texto: "Cada escopo da etapa 2 tem seus honorários. Marque um ou mais tipos: hora trabalhada, pró-labore, mensalidade, êxito ou permuta.",
        alvo: campo("Pró-labore"),
      },
      {
        titulo: "Valores e parcelas",
        texto: "Informe o valor total. Parcelado mensal: número de parcelas e data da 1ª; o valor de cada parcela sai sozinho.",
        alvo: () => campo("Valor Total")() ?? campo("Valor da hora")() ?? campo("Percentual")(),
      },
      {
        titulo: "Adicionais e desconto",
        texto: "“+ Pró-labore adicional” cobra outra fase ou instância. “Desconto?” registra a condição e o valor do desconto.",
        alvo: botao("+ Pró-labore adicional"),
      },
      {
        titulo: "Texto livre: prévia",
        texto: "Mexeu num texto livre (ex.: forma de pagamento)? Clique em “Ver prévia e aprovar” para ver como a cláusula fica no contrato.",
        alvo: botao("Ver prévia e aprovar"),
      },
    ],
  },
  {
    chave: "assistente-4",
    nome: "Novo contrato · etapa 4: Acessórios",
    passos: [
      {
        titulo: "Vigência",
        texto: "Data de início e de término, ou “Prazo indeterminado”.",
        alvo: campo("Vigência"),
      },
      {
        titulo: "Reembolso e multa",
        texto: "Diga se o cliente reembolsa despesas (com ou sem limite) e se há multa de 10% por atraso.",
        alvo: campo("Há reembolso de despesas"),
      },
      {
        titulo: "Diligências e deslocamento",
        texto: "Valor da diligência externa e custo por km, se forem cobrados.",
        alvo: campo("Valor da Diligência Externa"),
      },
      {
        titulo: "Cláusulas adicionais",
        texto: "Precisa de algo fora do padrão? “+ Adicionar cláusula” inclui um texto seu no contrato.",
        alvo: botao("+ Adicionar cláusula"),
      },
    ],
  },
  {
    chave: "assistente-5",
    nome: "Novo contrato · etapa 5: Ficha interna",
    passos: [
      {
        titulo: "Só para o escritório",
        texto: "Nada desta etapa vai para o contrato nem para o cliente. A ficha segue para o financeiro.",
        alvo: titulo("5."),
      },
      {
        titulo: "Contato financeiro do cliente",
        texto: "Quem cuida dos pagamentos do lado do cliente: nome, e-mail e telefone.",
        alvo: campo("Nome"),
      },
      {
        titulo: "Responsável pela gestão",
        texto: "Obrigatório: o advogado que acompanha o contrato.",
        alvo: campo("Responsável pela gestão"),
      },
      {
        titulo: "Participação",
        texto: "Se houver participação de advogados (captação, gestão), marque e informe o percentual ou valor de cada um.",
        alvo: campo("Este contrato terá participação"),
      },
    ],
  },
  {
    chave: "assistente-6",
    nome: "Novo contrato · etapa 6: Revisão",
    passos: [
      {
        titulo: "Confira tudo",
        texto: "Resumo de contratantes, escopos, honorários e acessórios. Achou erro? Clique na etapa lá em cima ou em “Anterior” e corrija.",
        alvo: titulo("6."),
      },
      {
        titulo: "Nada foi enviado ainda",
        texto: "O contrato só é gerado e enviado na etapa 7. Avance com “Próximo”.",
        alvo: botao("Próximo"),
      },
    ],
  },
  {
    chave: "assistente-7",
    nome: "Novo contrato · etapa 7: Envio",
    passos: [
      {
        titulo: "Quem assina pelo escritório",
        texto: "Obrigatório para enviar para assinatura. Sem ele, o botão de assinatura leva você até este campo.",
        alvo: sel("#socio-escritorio"),
      },
      {
        titulo: "E-mails e testemunhas",
        texto: "Confira o e-mail de cada contratante e inclua testemunhas se precisar. A testemunha do financeiro entra sozinha.",
        alvo: sel("#destinatario-0"),
      },
      {
        titulo: "Prévia do contrato",
        texto: "Veja como o Word vai ficar antes de enviar.",
        alvo: titulo("Prévia do contrato"),
      },
      {
        titulo: "Enviar",
        texto: ASSINATURA_X_EMAIL + " “Só salvar o contrato” grava sem mandar nada ao cliente.",
        alvo: botao("Enviar para assinatura digital"),
      },
    ],
  },
  {
    chave: "lista",
    nome: "Lista de contratos",
    passos: [
      {
        titulo: "Novo contrato",
        texto:
          "Escolha o tipo de contrato: honorários ou ação de consumo. Aditivo e distrato nascem na página do contrato; só para contrato antigo, feito fora do sistema, use o link discreto logo abaixo.",
        alvo: botao("Novo contrato"),
      },
      {
        titulo: "Buscar",
        texto: "Por nome, e-mail ou ID do contrato.",
        alvo: sel('input[placeholder^="Buscar"]'),
      },
      {
        titulo: "Cada linha",
        texto: "O nome abre o contrato. “Editar” só aparece enquanto o contrato ainda pode ser mudado (não enviado nem assinado).",
        alvo: sel("table"),
      },
    ],
  },
  {
    chave: "contrato",
    nome: "Página do contrato",
    passos: [
      {
        titulo: "Status",
        texto:
          "Rascunho: pode editar e enviar. Enviado: aguardando assinaturas no DocuSeal; para editar, use “Cancelar o envio e voltar a editar”. Assinado: não muda mais; para alterar, faça um aditivo.",
      },
      {
        titulo: "Ação principal",
        texto:
          "O botão em destaque é o próximo passo: em rascunho, enviar para assinatura; enviado, ver quem já assinou; assinado, baixar o Word.",
        alvo: () => botao("Enviar para assinatura digital")() ?? botao("Ver quem já assinou")() ?? botao("Baixar Word")(),
      },
      {
        titulo: "Mais ações",
        texto:
          "Cópia para conferência por e-mail, novo contrato a partir deste, cancelar o envio, registrar assinatura feita em papel e descartar o rascunho quando o cliente desiste. Cada item diz o que faz.",
        alvo: botao("Mais ações"),
      },
      {
        titulo: "Documentos deste contrato",
        texto: "Aditivo e distrato nascem aqui, com as partes já preenchidas. O substabelecimento sai junto com o distrato.",
        alvo: sel("#docs-do-contrato"),
      },
    ],
  },
  {
    chave: "financeiro",
    nome: "Setor financeiro",
    passos: [
      {
        titulo: "Pendentes",
        texto: "Fichas de participação que chegaram dos contratos. “Revisar e aprovar” confere e ativa a participação.",
      },
      {
        titulo: "Registrar x simular",
        texto: "“Registrar e calcular participação” grava o pagamento. “Simular (não grava)” só mostra a conta.",
      },
      {
        titulo: "Notas fiscais",
        texto: "Faturas e NFS-e ficam em “Emissão de NFS-e”.",
        alvo: botao("Emissão de NFS-e"),
      },
    ],
  },
  {
    chave: "emissao",
    nome: "Emissão de NFS-e",
    passos: [
      {
        titulo: "Faturas",
        texto:
          "Crie a fatura, aprove e depois “Emitir nota fiscal”: a nota vai para a prefeitura e não dá para desfazer daqui. Excluir pede confirmação.",
      },
      {
        titulo: "Notas emitidas",
        texto: "Acompanhe a situação, veja os detalhes e baixe o XML.",
      },
      {
        titulo: "Cadastros",
        texto: "Serviços, tomadores e dados do emissor (com o certificado) usados na emissão.",
      },
    ],
  },
];

/** Qual tour vale para a rota atual (null: tela sem tour). No assistente, o da etapa aberta. */
export function tourDaRota(pathname: string, etapa = 0): Tour | null {
  const chave =
    pathname === "/" || /^\/contracts\/[^/]+\/edit$/.test(pathname)
      ? `assistente-${etapa >= 1 && etapa <= 7 ? etapa : 1}`
      : pathname === "/contracts"
      ? "lista"
      : /^\/contracts\/[^/]+$/.test(pathname)
      ? "contrato"
      : pathname === "/financeiro"
      ? "financeiro"
      : pathname === "/financeiro/emissao"
      ? "emissao"
      : null;
  return TOURS.find((t) => t.chave === chave) ?? null;
}
