import { BACK } from "../playwright.config";
import { test, expect, entrar, api } from "./fixtures";

test.describe("login/convite", () => {
  test("link de convidado entra e abre a lista de contratos", async ({ page }) => {
    await entrar(page);
    await page.goto("/contracts");
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await expect(page).not.toHaveURL(/login|convite/);
  });

  test("token invalido nao entra", async ({ page }) => {
    await page.goto("/convite/token-falso-qa");
    await expect(page.getByText(/inv[aá]lido ou expirado/i)).toBeVisible({ timeout: 30_000 });
  });

  test("sem sessao, area interna manda para o login", async ({ page }) => {
    await page.goto("/contracts");
    await expect(page).toHaveURL(/login/);
  });

  test("API recusa sem token e aceita com token", async ({ request }) => {
    const sem = await request.get(`${BACK}/api/contracts`);
    expect(sem.status()).toBe(401);
    const com = await (await api()).get("/api/contracts");
    expect(com.status()).toBe(200);
  });
});
