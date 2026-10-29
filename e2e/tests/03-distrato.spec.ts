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

async function previa(page: Page) {
  await page.getByRole("button", { name: "Ver prévia" }).click();
  const quadro = page.frameLocator("iframe[title='Prévia do distrato']").locator("body");
  await expect(quadro).toContainText("DISTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS", { timeout: 60_000 });
  return quadro;
}

test.describe("distrato no modelo do escritorio", () => {
  test("sem valor: declaracao de quitacao integral e ressalva de exito marcada por padrao", async ({ page }) => {
    await abrir(page, "sem valor");
    await expect(page.getByLabel(/Ressalvar honorários de êxito/)).toBeChecked();
    const texto = await previa(page);
    await expect(texto).toContainText("honorários contratuais foram integralmente quitados");
    await expect(texto).not.toContainText("pagará ao Contratado");
    await expect(texto).not.toContainText("título executivo");
    await expect(texto).toContainText("honorários de sucumbência, nos termos do art. 23 da Lei n.º 8.906/94");
    await expect(texto).toContainText("proporcional ao trabalho realizado");
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
    await page.getByLabel(/Envolve processo judicial/).check();
    const subst = page.getByLabel("Substabelecer sem reserva de poderes e devolver documentos");
    await expect(subst).toBeChecked();
    await subst.uncheck({ force: true }).catch(() => {});
    await expect(subst).toBeChecked(); // travado enquanto houver processo

    // Sem os dados do substabelecimento, nao passa.
    await page.getByRole("button", { name: "Ver prévia" }).click();
    await expect(page.locator("iframe[title='Prévia do distrato']")).toHaveCount(0);

    // Substabelecente (cadastro), substabelecido e processo.
    await page.locator("select").filter({ hasText: "Colaborador" }).first().selectOption({ label: "Ana Teste Socia" });
    await page.getByRole("button", { name: "Adicionar", exact: true }).first().click();
    const nome = page.getByLabel(/^Nome/).last();
    await nome.fill(`${MARCA} Novo Patrono`);
    // O cartao do substabelecido: o ancestral mais proximo da caixa de nome que tambem tem o campo de OAB.
    await nome.locator("xpath=ancestor::div[.//input[@placeholder='00.000']][1]").getByPlaceholder("00.000").fill("55555");
    await page.getByLabel("Número (CNJ)").fill(CNJ);
    const texto = await previa(page);
    await expect(texto).toContainText("10 (dez) dias");
    await expect(texto).toContainText("sem reserva de poderes");
    await expect(texto).toContainText("art. 5º, § 3º, da Lei n.º 8.906/94");
    await expect(texto).toContainText("mediante recibo");

    await page.getByRole("button", { name: /Gerar distrato/ }).click();
    await expect(page.getByText(/gerado|sucesso/i).first()).toBeVisible({ timeout: 60_000 });
    const docs = await (await api()).get(`/api/contracts/${origem.id}/documentos`);
    const tipos = ((await docs.json()).documentos as { tipo_contrato: string }[]).map((d) => d.tipo_contrato).sort();
    expect(tipos).toEqual(["distrato", "substabelecimento"]);
  });
});
