import { expect, test } from "@playwright/test";

import { injectAuth, registerAndToken } from "./helpers";

test.describe("chat", () => {
  test("a diagnosis request is refused with a safe reframe", async ({ page, context, request }) => {
    const { token } = await registerAndToken(request);
    await injectAuth(context, token);
    await page.goto("/chat");

    const box = page.getByPlaceholder(/Ask about a result/i);
    await box.fill("What disease do I have?");
    await box.press("Enter");

    // The refusal bubble reframes to the educational scope (these phrases are unique to the
    // bubble — the page subtitle separately mentions "I can't diagnose, prescribe…").
    await expect(page.getByText(/not a doctor/i)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/not able to tell you what condition/i)).toBeVisible();
    await expect(page.getByText(/Consult a licensed healthcare professional/i).first()).toBeVisible();
  });

  test("an educational question returns a hedged, disclaimer-bearing answer", async ({
    page,
    context,
    request,
  }) => {
    const { token } = await registerAndToken(request);
    await injectAuth(context, token);
    await page.goto("/chat");

    const box = page.getByPlaceholder(/Ask about a result/i);
    await box.fill("What does hemoglobin measure?");
    await box.press("Enter");

    await expect(page.getByText(/Hemoglobin is/i)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/Consult a licensed healthcare professional/i).first()).toBeVisible();
  });
});
