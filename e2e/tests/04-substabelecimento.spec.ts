import { test, expect, entrar, MARCA, type Page } from "./fixtures";

const CNJ = "1234567-49.2020.8.13.0024"; // digito verificador valido, TJMG
const CNJ_DV_ERRADO = "1234567-00.2020.8.13.0024";

async function abrir(page: Page) {
  await entrar(page);
  await page.goto("/documentos/novo?tipo=substabelecimento");
  await expect(page.getByText("Data do substabelecimento")).toBeVisible({ timeout: 60_000 });
}

async function preencherBase(page: Page) {
  await page.getByLabel("Pessoa jurídica").check();
  await page.getByLabel(/^Razão social/).fill(`${MARCA} Empresa Substabelecimento Ltda`);
  await page.locator("select").filter({ hasText: "Colaborador" }).first().selectOption({ label: "Ana Teste Socia" });
  await page.getByRole("button", { name: "Adicionar", exact: true }).first().click();
  const nome = page.getByLabel(/^Nome/).last();
  await nome.fill(`${MARCA} Novo Patrono`);
  await nome.locator("xpath=ancestor::div[.//input[@placeholder='00.000']][1]").getByPlaceholder("00.000").fill("55555");
}

test.describe("substabelecimento com consulta pelo CNJ", () => {
  test("ao sair do numero CNJ mostra o tribunal", async ({ page }) => {
    await abrir(page);
    const campo = page.getByLabel(/Número \(CNJ\)/);
    await campo.fill(CNJ);
    await campo.blur();
    await expect(page.getByText("Tribunal de Justiça (MG)")).toBeVisible({ timeout: 30_000 });
  });

  test("numero com digito verificador errado e' recusado na tela", async ({ page }) => {
    await abrir(page);
    const campo = page.getByLabel(/Número \(CNJ\)/);
    await campo.fill(CNJ_DV_ERRADO);
    await campo.blur();
    await expect(page.getByText(/inválid|dígito|verificador/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("importa processos de planilha CSV", async ({ page }) => {
    await abrir(page);
    await page.locator("input[type=file]").setInputFiles({
      name: "processos.csv", mimeType: "text/csv", buffer: Buffer.from(`Número;Tipo\n${CNJ};Processo\n`),
    });
    await expect(page.getByLabel(/Número \(CNJ\)/).first()).toHaveValue(CNJ, { timeout: 30_000 });
  });

  test("gera a previa com partes e processo", async ({ page }) => {
    await abrir(page);
    await preencherBase(page);
    await page.getByLabel(/Número \(CNJ\)/).fill(CNJ);
    await page.getByRole("button", { name: "Ver prévia" }).click();
    const texto = page.frameLocator("iframe[title='Prévia do substabelecimento']").locator("body");
    await expect(texto).toContainText(/SUBSTABELECIMENTO/i, { timeout: 60_000 });
    await expect(texto).toContainText(CNJ);
    await expect(texto).toContainText(/EMPRESA SUBSTABELECIMENTO LTDA/i);
    await expect(texto).toContainText(/sem reserva de poderes/i);
  });
});
