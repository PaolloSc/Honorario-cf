import { test, expect, entrar, MARCA, type Page } from "./fixtures";

const CNPJ_PUBLICO = "04124308000108"; // Astra Sistemas e Informatica Ltda (dado publico); socios no QSA
const CNPJ_MASCARADO = "04.124.308/0001-08";
const AVISO = "Preencha os campos obrigatórios antes de avançar";

/** Próximo usa aria-disabled (nao `disabled`): o clique mostra o que falta em vez de ficar mudo. */
const clicarProximo = (page: Page) => page.getByRole("button", { name: "Próximo" }).click({ force: true });

test.describe("contrato de honorarios: wizard ate a previa", () => {
  test("PF + consultoria contratual + mensalidade chega ao passo 7", async ({ page }) => {
    await entrar(page);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Novo Contrato de Honorários/ })).toBeVisible();
    const prox = async () => { await page.getByRole("button", { name: "Próximo" }).click(); await page.waitForTimeout(1200); };
    const principal = () => page.locator("main");

    // 1a. Obrigatorios marcados com * e, ao clicar Proximo vazio, a lista do que falta.
    await expect(page.locator("label").filter({ hasText: /Nome completo/ }).first()).toContainText("*");
    await expect(page.locator("label").filter({ hasText: /^CPF/ }).first()).toContainText("*");
    await clicarProximo(page);
    await expect(page.getByText(AVISO)).toBeVisible();
    await expect(page.getByText("Contratante 1: informe o nome completo.")).toBeVisible();
    await expect(page.getByText("Contratante 1: informe o CPF.")).toBeVisible();
    await expect(page.getByText("Contratante 1: informe o endereço completo.")).toBeVisible(); // estado civil ja vem "Solteiro(a)"
    await expect(page.getByText("Contratante 1: informe um e-mail válido.")).toBeVisible();

    // 1b. Contratante (PF). O endereco vem do CEP.
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
    await clicarProximo(page); // sem responsavel nao avanca e diz o motivo
    await expect(page.getByText("Informe o responsável pela gestão do contrato.")).toBeVisible();
    await expect(page.getByRole("heading", { name: /Ficha Interna/ })).toBeVisible();
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

  test("PJ: CNPJ consulta sozinho com 14 digitos; e-mail da empresa obrigatorio; e-mail do representante opcional", async ({ page }) => {
    await entrar(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Pessoa Jurídica" }).first().click();
    const cnpj = page.getByPlaceholder("00.000.000/0000-00 ou 12.ABC.345/01DE-35");
    const chamadas: string[] = [];
    page.on("request", (r) => { if (/\/api\/cnpj\//.test(r.url())) chamadas.push(r.url().split("/").pop()!); });

    // Com 13 digitos nao consulta; no 14o consulta uma vez so, sem clicar Buscar.
    await cnpj.pressSequentially(CNPJ_PUBLICO.slice(0, 13), { delay: 60 });
    await page.waitForTimeout(1500);
    expect(chamadas).toEqual([]);
    await cnpj.pressSequentially(CNPJ_PUBLICO.slice(13), { delay: 60 });
    await expect(page.getByLabel(/Razão Social/)).not.toHaveValue("", { timeout: 40_000 });
    await expect(page.getByLabel(/Endereço da sede/)).not.toHaveValue("");
    expect(chamadas).toEqual([CNPJ_PUBLICO]);

    // Sem e-mail da empresa: bloqueia dizendo o que falta.
    await clicarProximo(page);
    await expect(page.getByText(AVISO)).toBeVisible();
    await expect(page.getByText("Contratante 1: informe um e-mail válido.")).toBeVisible();

    // Representante do QSA com e-mail invalido: bloqueia com mensagem clara.
    await page.getByLabel(/Adicionar dados do\(s\) representante/).check();
    await page.getByRole("button", { name: /^Preencher:/ }).first().click();
    await page.getByLabel("E-mail do Representante").first().fill("email-invalido");
    await page.getByPlaceholder("contato@empresa.com").fill("qa-teste@example.com");
    await clicarProximo(page);
    await expect(page.getByText(/e-mail inválido do representante/)).toBeVisible();

    // E-mail do representante e' opcional: vazio avanca (assina o e-mail da empresa).
    await page.getByLabel("E-mail do Representante").first().fill("");
    await clicarProximo(page);
    await expect(page.getByRole("heading", { name: /Escopo/ })).toBeVisible({ timeout: 15_000 });
  });

  test("regressao #168: campo CNPJ continua com 14 digitos depois da consulta automatica", async ({ page }) => {
    await entrar(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Pessoa Jurídica" }).first().click();
    const cnpj = page.getByPlaceholder("00.000.000/0000-00 ou 12.ABC.345/01DE-35");
    await cnpj.pressSequentially(CNPJ_PUBLICO, { delay: 80 });
    await expect(page.getByLabel(/Razão Social/)).not.toHaveValue("", { timeout: 40_000 });
    await page.waitForTimeout(2000); // a consulta terminou; o campo nao pode voltar a 13 digitos
    await expect(cnpj).toHaveValue(CNPJ_MASCARADO);
  });
});
