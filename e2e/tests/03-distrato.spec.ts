import { test, expect, entrar, api, criarContratoOrigem, MARCA, type Page } from "./fixtures";

const CNJ = "1234567-49.2020.8.13.0024"; // numero de teste com digito verificador valido

async function abrir(page: Page, sufixo: string) {
  const origem = await criarContratoOrigem(await api(), sufixo);
  await entrar(page);
  await page.goto(`/documentos/novo?tipo=distrato&origem=${origem.id}`);
  await expect(page.getByText("Data do distrato")).toBeVisible({ timeout: 60_000 });
  await page.getByLabel("Data do contrato original").fill("2024-03-09");
  await page.getByLabel("Objeto do contrato original").fill(`assessoria jurídica ${MARCA}`);
  return origem;
}

/** O substabelecimento sempre sai junto com o distrato: substabelecente, substabelecido (OAB) e processo sao obrigatorios. */
async function preencherSubstabelecimento(page: Page) {
  await page.locator("select").filter({ hasText: "Colaborador" }).first().selectOption({ label: "Ana Teste Socia" });
  await page.getByRole("button", { name: "Adicionar", exact: true }).first().click();
  const nome = page.getByLabel(/^Nome/).last();
  await nome.fill(`${MARCA} Novo Patrono`);
  // O cartao do substabelecido: o ancestral mais proximo da caixa de nome que tambem tem o campo de OAB.
  await nome.locator("xpath=ancestor::div[.//input[@placeholder='00.000']][1]").getByPlaceholder("00.000").fill("55555");
  await page.getByLabel("Número (CNJ)").fill(CNJ);
}

async function previa(page: Page) {
  await preencherSubstabelecimento(page);
  await page.getByRole("button", { name: "Ver prévia" }).click();
  const quadro = page.frameLocator("iframe[title='Prévia do distrato']").locator("body");
  await expect(quadro).toContainText("DISTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS", { timeout: 60_000 });
  return quadro;
}

test.describe("distrato no modelo do escritorio", () => {
  test("sem valor: declaracao de quitacao integral e ressalva de exito marcada por padrao", async ({ page }) => {
    await abrir(page, "sem valor");
    // So vem marcado quando o contrato de origem tem honorario de exito; a origem do teste e' mensalidade.
    await expect(page.getByLabel(/Ressalvar honorários de êxito/)).not.toBeChecked();
    await page.getByLabel(/Ressalvar honorários de êxito/).check();
    const texto = await previa(page);
    await expect(texto).toContainText("foram integralmente pagos, nada havendo a pagar a qualquer título");
    await expect(texto).not.toContainText("pagará ao Contratado");
    await expect(texto).not.toContainText("título executivo");
    await expect(texto).toContainText("honorários de sucumbência, nos termos do art. 23 da Lei n.º 8.906/94");
    await expect(texto).toContainText("êxito");
    await expect(texto).not.toContainText(/R\$ 0,00|undefined|\[object/);
  });

  test("sem ressalva: quitacao total, sem excecao de exito", async ({ page }) => {
    await abrir(page, "sem ressalva");
    await page.getByLabel(/Ressalvar honorários de êxito/).uncheck();
    const texto = await previa(page);
    await expect(texto).toContainText("mútua, total, completa, irrevogável e irretratável quitação");
    await expect(texto).not.toContainText("ressalvados os honorários de êxito");
  });

  test("com valor: multa 10%, juros 1% a.m., correcao e titulo executivo", async ({ page }) => {
    await abrir(page, "com valor");
    await page.getByLabel("Valor (R$)").fill("4.000"); // milhar com ponto: tem que dar R$ 4.000,00, nao R$ 4,00
    await page.getByLabel("Data limite").fill("2030-11-30");
    const texto = await previa(page);
    await expect(texto).toContainText("até o dia 30/11/2030, o valor de R$ 4.000,00 (quatro mil reais)");
    await expect(texto).toContainText("multa de 10% (dez por cento)");
    await expect(texto).toContainText("juros de 1% (um por cento) ao mês");
    await expect(texto).toContainText("correção monetária");
    await expect(texto).toContainText("art. 784, III, do Código de Processo Civil");
    await expect(texto).not.toContainText("integralmente quitados");
  });

  test("valor sem data limite nao gera previa", async ({ page }) => {
    await abrir(page, "valor sem data");
    await page.getByLabel("Valor (R$)").fill("1.000,00");
    await page.getByRole("button", { name: "Ver prévia" }).click();
    await expect(page.getByText("Informe a data limite do pagamento")).toBeVisible();
    await expect(page.locator("iframe[title='Prévia do distrato']")).toHaveCount(0);
  });

  test("contencioso: o substabelecimento e' obrigatorio e sai junto com o distrato", async ({ page }) => {
    const origem = await abrir(page, "contencioso");
    // A secao "Substabelecimento gerado junto" e' sempre obrigatoria (nao ha mais caixa "envolve processo judicial").
    await expect(page.getByText("Substabelecimento gerado junto")).toBeVisible();

    // Sem os dados do substabelecimento, nao passa.
    await page.getByRole("button", { name: "Ver prévia" }).click();
    await expect(page.locator("iframe[title='Prévia do distrato']")).toHaveCount(0);

    // Substabelecente (cadastro), substabelecido e processo (feitos dentro de previa()).
    const texto = await previa(page);
    await expect(texto).toContainText("10 (dez) dias");
    await expect(texto).toContainText("sem reserva de poderes");
    await expect(texto).toContainText("art. 9º do Código de Ética e Disciplina da OAB");
    await expect(texto).toContainText("restituirá os documentos e bens recebidos, com prestação de contas");

    await page.getByRole("button", { name: /Gerar distrato/ }).click();
    // /gerado/ casaria com o titulo "Substabelecimento gerado junto": confere pela API, esperando a geracao terminar.
    await expect
      .poll(
        async () => {
          const docs = await (await api()).get(`/api/contracts/${origem.id}/documentos`);
          return ((await docs.json()).documentos as { tipo_contrato: string }[]).map((d) => d.tipo_contrato).sort();
        },
        { timeout: 60_000 },
      )
      .toEqual(["distrato", "substabelecimento"]);
  });
});
