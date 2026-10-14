import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * Las pruebas E2E arrancan dos servidores propios:
 *
 * - La API del backend en 127.0.0.1:8100, migrada con Alembic sobre
 *   data/e2e.sqlite (ignorado por git).
 * - El frontend en localhost:3100, apuntando a esa API.
 *
 * Puertos distintos de los de desarrollo (3000 y 8000), para no mezclar datos.
 *
 * Variables opcionales:
 * - NOVEL_ENGINE_PYTHON: intérprete Python con las dependencias de backend
 *   instaladas. Por defecto, backend/.venv/bin/python.
 * - PLAYWRIGHT_CHROMIUM_EXECUTABLE: ruta a un Chromium ya instalado.
 */
const repoRoot = path.resolve(__dirname, "..", "..");
const backendDir = path.join(repoRoot, "backend");
const python = process.env.NOVEL_ENGINE_PYTHON ?? path.join(backendDir, ".venv", "bin", "python");
const e2eDatabase = path.join(repoRoot, "data", "e2e.sqlite");
const apiUrl = "http://127.0.0.1:8100";
const webUrl = "http://localhost:3100";
const chromiumExecutable = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: webUrl,
    trace: "retain-on-failure",
  },
  projects: [
    {
      // Pruebas unitarias del guardado: sin navegador, con temporizadores controlados.
      name: "unit",
      testDir: "./tests/unit",
    },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: chromiumExecutable ? { executablePath: chromiumExecutable } : {},
      },
    },
  ],
  webServer: [
    {
      command: `"${python}" -m alembic upgrade head && "${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8100`,
      cwd: backendDir,
      url: `${apiUrl}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        DATABASE_URL: `sqlite:///${e2eDatabase}`,
        NOVEL_ENGINE_CORS_ORIGINS: webUrl,
        // Las copias automáticas se prueban en el backend (pytest). Aquí no añaden nada.
        NOVEL_ENGINE_BACKUP_INTERVAL_MINUTES: "0",
      },
    },
    {
      command: "npx next dev --port 3100",
      url: webUrl,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        NEXT_PUBLIC_API_BASE_URL: apiUrl,
        // Directorio de compilación propio (ver next.config.mjs).
        NOVEL_ENGINE_E2E: "1",
      },
    },
  ],
});
