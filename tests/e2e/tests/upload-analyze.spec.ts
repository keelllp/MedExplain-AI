import { expect, test } from "@playwright/test";

import { FIXTURE_PDF, injectAuth, registerAndToken } from "./helpers";

test("upload a report, analyze it, and view the results", async ({ page, context, request }) => {
  const { token } = await registerAndToken(request);
  await injectAuth(context, token);

  await page.goto("/upload");
  // The file input is visually hidden inside the dropzone label; setInputFiles still works.
  await page.locator('input[type="file"]').setInputFiles(FIXTURE_PDF);
  await page.getByRole("button", { name: /upload & analyze/i }).click();

  // The upload page polls analysis, then redirects to the report.
  await page.waitForURL(/\/reports\/\d+/, { timeout: 60_000 });

  // The analyzed report shows extracted biomarkers + a guarded summary.
  await expect(page.getByText("Biomarkers")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Hemoglobin").first()).toBeVisible();
  await expect(page.getByText(/Consult a licensed healthcare professional/i).first()).toBeVisible();
});
