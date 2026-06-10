import { expect, test } from "@playwright/test";

import { injectAuth, registerAndToken, uploadAndAnalyze } from "./helpers";

test("a trend chart renders for a marker measured across two reports", async ({
  page,
  context,
  request,
}) => {
  const { token } = await registerAndToken(request);
  // Two analyzed reports → hemoglobin has >= 2 numeric points → it becomes trendable.
  await uploadAndAnalyze(request, token);
  await uploadAndAnalyze(request, token);
  await injectAuth(context, token);

  await page.goto("/trends");
  await expect(page.getByRole("heading", { name: /Trends over time/i })).toBeVisible();

  // The custom dropdown defaults to a trendable marker (its label shows the 2-point count),
  // and the SVG chart renders. (The fixture has several markers; which one defaults isn't
  // asserted — only that a 2-point series is selected and charted.)
  await expect(page.getByRole("button", { name: "Biomarker" })).toContainText("(2)", {
    timeout: 20_000,
  });
  await expect(page.locator("svg[role='img']")).toBeVisible();

  // The data-only surface still carries the disclaimer caption.
  await expect(page.getByText(/Consult a licensed healthcare professional/i).first()).toBeVisible();
});

test("a new account with no repeated markers sees the empty state", async ({
  page,
  context,
  request,
}) => {
  const { token } = await registerAndToken(request);
  await injectAuth(context, token);
  await page.goto("/trends");
  await expect(page.getByText(/No trends yet/i)).toBeVisible();
});
