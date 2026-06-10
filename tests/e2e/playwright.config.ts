import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

// Isolated E2E stack on dedicated ports so it never disturbs the dev stack (3000/8000):
//  - backend on 8123 with its own SQLite DB + offline LLM (deterministic, no egress)
//  - frontend on 3123 with its own .next build dir (NEXT_DIST_DIR) pointing at that backend
const BACKEND_PORT = 8123;
const FRONTEND_PORT = 3123;
const API_BASE = `http://127.0.0.1:${BACKEND_PORT}/api/v1`;
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;

const backendDir = path.join(__dirname, "..", "..", "backend");
const frontendDir = path.join(__dirname, "..", "..", "frontend");
const venvPython = process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python";
const e2eDb = path.join(__dirname, "e2e.db");

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false, // single backend worker + shared DB → serial
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: FRONTEND_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${venvPython} -m uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT} --workers 1`,
      cwd: backendDir,
      url: `http://127.0.0.1:${BACKEND_PORT}/health`,
      timeout: 60_000,
      reuseExistingServer: true,
      env: {
        MEDEXPLAIN_ENV: "dev",
        MEDEXPLAIN_DB_PATH: e2eDb,
        MEDEXPLAIN_DEFAULT_LLM_MODE: "offline", // deterministic; no Gemini egress in E2E
        MEDEXPLAIN_GEMINI_API_KEY: "",
        MEDEXPLAIN_OLLAMA_HOST: "http://127.0.0.1:9", // dead → offline-template floor
        MEDEXPLAIN_CORS_ORIGINS: `${FRONTEND_URL},http://localhost:${FRONTEND_PORT}`,
      },
    },
    {
      // Production build + start (NOT `next dev`): precompiled routes mean no Turbopack
      // on-demand compile races (which let Playwright interact before React hydrated), and
      // NEXT_PUBLIC_API_BASE_URL is reliably inlined at build time. Builds to its own dir so
      // the main dev server's .next is untouched.
      command: `npm run build && npm run start -- --port ${FRONTEND_PORT}`,
      cwd: frontendDir,
      url: FRONTEND_URL,
      timeout: 240_000,
      reuseExistingServer: true,
      env: {
        NEXT_PUBLIC_API_BASE_URL: API_BASE,
        NEXT_DIST_DIR: ".next-e2e",
      },
    },
  ],
});
