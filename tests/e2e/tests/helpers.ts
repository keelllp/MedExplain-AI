import fs from "node:fs";
import path from "node:path";

import type { APIRequestContext, BrowserContext } from "@playwright/test";

export const API = "http://127.0.0.1:8123/api/v1";
export const FIXTURE_PDF = path.join(__dirname, "..", "fixtures", "sample-cbc.pdf");

export function uniqueEmail(): string {
  return `e2e-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}@example.com`;
}

/** Register + log in via the API; returns a bearer token (faster/less flaky than UI setup). */
export async function registerAndToken(
  request: APIRequestContext,
  email = uniqueEmail(),
  password = "password123",
): Promise<{ email: string; password: string; token: string }> {
  await request.post(`${API}/auth/register`, { data: { email, password } });
  const res = await request.post(`${API}/auth/login`, { data: { email, password } });
  const token = (await res.json()).access_token as string;
  return { email, password, token };
}

/** Inject a JWT into localStorage so the app boots authenticated (the key api.ts uses). */
export async function injectAuth(context: BrowserContext, token: string): Promise<void> {
  await context.addInitScript((t) => {
    window.localStorage.setItem("medexplain_token", t as string);
  }, token);
}

/** Upload the fixture PDF + analyze it via the API, polling until analyzed. Returns report id. */
export async function uploadAndAnalyze(request: APIRequestContext, token: string): Promise<number> {
  const auth = { Authorization: `Bearer ${token}` };
  const up = await request.post(`${API}/reports/upload`, {
    headers: auth,
    multipart: {
      file: { name: "cbc.pdf", mimeType: "application/pdf", buffer: fs.readFileSync(FIXTURE_PDF) },
    },
  });
  const reportId = (await up.json()).report_id as number;
  await request.post(`${API}/reports/analyze`, { headers: auth, data: { report_id: reportId } });
  for (let i = 0; i < 80; i++) {
    const detail = await (await request.get(`${API}/reports/${reportId}`, { headers: auth })).json();
    if (detail.status === "analyzed") return reportId;
    if (detail.status === "failed") throw new Error(`analyze failed in setup (report ${reportId})`);
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`analyze timed out in setup (report ${reportId})`);
}
