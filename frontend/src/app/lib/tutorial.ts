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

const ASSINATURA_X_EMAIL =
  "“Enviar para assinatura digital” manda o link do DocuSeal a cada signatário e bloqueia a edição. " +
  "“Enviar cópia para conferência” só manda o Word por e-mail para o cliente revisar; não é assinatura. " +
  "As duas pedem confirmação mostrando quem vai receber.";

export const TOURS: Tour[] = [
  {
    chave: "assistente",
    nome: "Novo contrato (assistente)",
    passos: [
      {
        titulo: "Contrato em 7 etapas",
        texto:
          "Preencha cada etapa e avance com “Próximo”. O que você digita é salvo sozinho como rascunho: dá para sair e continuar depois.",
      },
      {
        titulo: "Próximo",
        texto: "Só libera quando os campos obrigatórios da etapa estão preenchidos; a lista em vermelho diz o que falta.",
        alvo: botao("Próximo"),
      },
      {
        titulo: "Etapa 7: enviar",
        texto: ASSINATURA_X_EMAIL + " “Só salvar o contrato” grava sem mandar nada ao cliente.",
      },
      {
        titulo: "Quem assina pelo escritório",
        texto: "Obrigatório para enviar para assinatura. Sem ele, o botão de assinatura leva você até este campo.",
        alvo: sel("#socio-escritorio"),
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

/** Qual tour vale para a rota atual (null: tela sem tour). */
export function tourDaRota(pathname: string): Tour | null {
  const chave =
    pathname === "/" || /^\/contracts\/[^/]+\/edit$/.test(pathname)
      ? "assistente"
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
