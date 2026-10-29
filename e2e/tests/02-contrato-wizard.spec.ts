import { test, expect, entrar, MARCA } from "./fixtures";

test.describe("contrato de honorarios: wizard ate a previa", () => {
  test("PF + consultoria contratual + mensalidade chega ao passo 7", async ({ page }) => {
    await entrar(page);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Novo Contrato de Honorários/ })).toBeVisible();
    const prox = async () => { await page.getByRole("button", { name: "Próximo" }).click(); await page.waitForTimeout(1200); };
    const principal = () => page.locator("main");

    // 1. Contratante (PF). O endereco vem do CEP.
    await page.getByPlaceholder("Nome completo").fill(`${MARCA} Maria Wizard`);
    await page.getByPlaceholder("000.000.000-00").fill("529.982.247-25");
    await page.locator("select").first().selectOption({ label: "Casado(a)" });
    await page.getByPlaceholder("email@exemplo.com").fill("qa@exemplo.com");
    await page.getByPlaceholder("00000-000").fill("30112-010");
    await page.getByPlaceholder("Ex: 271").fill("271");
    await expect(page.getByPlaceholder("Preenchido automaticamente pelo CEP")).not.toHaveValue("", { timeout: 20_000 });
    await prox();

    // 2. Escopo
    await expect(page.getByRole("heading", { name: /Escopo/ })).toBeVisible();
    await page.getByLabel("Consultoria para análise, revisão e negociação contratual").check();
    await prox();

    // 3. Honorarios: mensalidade. O campo de valor e' mascarado em centavos ("250000" -> 2.500,00).
    await page.getByLabel("Mensalidade", { exact: true }).check();
    await page.getByPlaceholder("0,00").first().fill("250000");
    await page.getByLabel("Prazo indeterminado").first().check();
    await prox();

    // 4. Acessorios (padroes)
    await expect(page.getByRole("heading", { name: /Acessórios/ })).toBeVisible();
    await prox();

    // 5. Ficha interna: responsavel pela gestao e' obrigatorio.
    await expect(page.getByRole("heading", { name: /Ficha Interna/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "Próximo" })).toBeDisabled(); // sem responsavel nao avanca
    await page.getByPlaceholder("Busque por nome ou letra").fill("a");
    await page.locator("ul li").filter({ hasText: "Ana Teste" }).first().click();
    await prox();

    // 6. Revisao: confere o que foi digitado, com o valor formatado.
    await expect(page.getByRole("heading", { name: /Revisão do Contrato/ })).toBeVisible();
    await expect(principal()).toContainText(`${MARCA} Maria Wizard`);
    await expect(principal()).toContainText("529.982.247-25");
    await expect(principal()).toContainText(/R\$\s*2\.500,00\/mês/);
    await prox();

    // 7. Envio: so inspeciona; nao envia e-mail nem assinatura.
    await expect(principal()).toContainText(/Etapa 7 de 7|Envio/);
    const previa = page.frameLocator("iframe[title=\"Prévia do contrato\"]");
    await expect(previa.locator("body")).toContainText("CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS", { timeout: 60_000 });
    await expect(previa.locator("body")).toContainText(/\[TESTE-QA-DELETAR\] MARIA WIZARD/i);
    await expect(previa.locator("body")).toContainText("R$ 2.500,00");
    // Para aqui de proposito: "Apenas Gerar" tambem tenta mandar a ficha de participacao ao financeiro por e-mail.
    await expect(page.getByRole("button", { name: "Apenas Gerar Contrato" })).toBeEnabled();
  });
});
