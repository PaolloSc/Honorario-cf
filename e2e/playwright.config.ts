import { defineConfig } from "@playwright/test";

// O alvo vem de E2E_FRONT/E2E_BACK (URLs de homolog nao ficam no repositorio publico). Producao e' recusada em fixtures.ts. O token do convite vem do ambiente, nunca do repo.
export const FRONT = process.env.E2E_FRONT ?? "";
export const BACK = process.env.E2E_BACK ?? "";

export default defineConfig({
  testDir: "./tests",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1, // homolog compartilha um banco; os testes criam dados e dependem de ordem
  fullyParallel: false,
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "report/result.json" }], ["html", { outputFolder: "report/html", open: "never" }]],
  outputDir: "report/artifacts",
  use: {
    baseURL: FRONT,
    channel: "chrome", // Chrome instalado; evita baixar navegador
    headless: true,
    viewport: { width: 1366, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    locale: "pt-BR",
  },
});
