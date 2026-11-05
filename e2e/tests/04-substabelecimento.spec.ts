import { test, expect, entrar, api, criarContratoOrigem, type Page } from "./fixtures";

// O substabelecimento avulso foi removido (#157, #158): ele nasce sempre junto com o distrato.
// Estes testes cobrem a rota antiga e a secao "Substabelecimento gerado junto" do formulario de distrato.
const CNJ = "1234567-49.2020.8.13.0024"; // digito verificador valido, TJMG
const CNJ_DV_ERRADO = "1234567-00.2020.8.13.0024";

async function abrirDistrato(page: Page, sufixo: string) {
  const origem = await criarContratoOrigem(await api(), sufixo);
  await entrar(page);
  await page.goto(`/documentos/novo?tipo=distrato&origem=${origem.id}`);
  await expect(page.getByText("Data do distrato")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Substabelecimento gerado junto")).toBeVisible();
}

test.describe("substabelecimento: sempre junto com o distrato", () => {
  test("rota avulsa antiga explica que nao existe mais", async ({ page }) => {
    await entrar(page);
    await page.goto("/documentos/novo?tipo=substabelecimento");
    await expect(page.getByText(/gerado junto com o distrato/)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByLabel(/Número \(CNJ\)/)).toHaveCount(0);
  });

  test("no distrato, ao sair do numero CNJ mostra o tribunal", async ({ page }) => {
    await abrirDistrato(page, "cnj tribunal");
    const campo = page.getByLabel(/Número \(CNJ\)/).first();
    await campo.fill(CNJ);
    await campo.blur();
    await expect(page.getByText("Tribunal de Justiça (MG)")).toBeVisible({ timeout: 30_000 });
  });

  test("no distrato, numero com digito verificador errado e' recusado", async ({ page }) => {
    await abrirDistrato(page, "cnj dv");
    const campo = page.getByLabel(/Número \(CNJ\)/).first();
    await campo.fill(CNJ_DV_ERRADO);
    await campo.blur();
    await expect(page.getByText(/inválid|dígito|verificador/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("no distrato, importa processos de planilha CSV", async ({ page }) => {
    await abrirDistrato(page, "csv");
    await page.locator("input[type=file]").setInputFiles({
      name: "processos.csv", mimeType: "text/csv", buffer: Buffer.from(`Número;Tipo\n${CNJ};Processo\n`),
    });
    await expect(page.getByLabel(/Número \(CNJ\)/).first()).toHaveValue(CNJ, { timeout: 30_000 });
  });
});
