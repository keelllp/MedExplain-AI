import { expect, test } from "@playwright/test";

import { injectAuth, registerAndToken } from "./helpers";

test.describe("account / LLM settings", () => {
  test("defaults to offline; selecting cloud without a server key is blocked", async ({
    page,
    context,
    request,
  }) => {
    const { token } = await registerAndToken(request); // E2E backend defaults new users to offline
    await injectAuth(context, token);
    await page.goto("/profile");

    // Offline is the active engine by default.
    await expect(page.getByRole("button", { name: /Offline \(Ollama\)/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    // Switching to cloud fires a consent confirm; accept it, then the server (no Gemini key
    // in E2E) rejects the switch and the UI surfaces the not-available message.
    page.once("dialog", (d) => d.accept());
    await page.getByRole("button", { name: /Cloud \(Gemini\)/ }).click();
    await expect(page.getByText(/not available on this server/i)).toBeVisible();
  });
});
