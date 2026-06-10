import { expect, test } from "@playwright/test";

import { API, uniqueEmail } from "./helpers";

test.describe("authentication", () => {
  test("sign up and land on the dashboard", async ({ page }) => {
    const email = uniqueEmail();
    await page.goto("/signup");
    await page.locator("#email").fill(email);
    await page.locator("#password").fill("password123");
    await page.locator("#confirm").fill("password123");
    await page.getByRole("checkbox").check(); // the educational-tool acknowledgement
    await page.getByRole("button", { name: /create account/i }).click();

    await page.waitForURL("**/dashboard");
    // The authed nav (only shown when logged in) exposes the Upload link (exact: the empty
    // dashboard also has an "Upload report" CTA link).
    await expect(page.getByRole("link", { name: "Upload", exact: true })).toBeVisible();
  });

  test("log in with an existing account", async ({ page, request }) => {
    const email = uniqueEmail();
    await request.post(`${API}/auth/register`, { data: { email, password: "password123" } });

    await page.goto("/login");
    await page.locator("#email").fill(email);
    await page.locator("#password").fill("password123");
    await page.getByRole("button", { name: /log in/i }).click();

    await page.waitForURL("**/dashboard");
    await expect(page.getByRole("link", { name: "Chat" })).toBeVisible();
  });

  test("a protected page redirects an unauthenticated visitor to login", async ({ page }) => {
    await page.goto("/trends");
    await page.waitForURL("**/login");
  });
});
