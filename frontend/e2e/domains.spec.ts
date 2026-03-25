import { expect, test } from "@playwright/test";

import { loginAsSuperAdmin } from "./auth";

function uniqueDomain(): string {
  return `playwright-${Date.now()}-${Math.random().toString(36).slice(2, 6)}.example.com`;
}

test.describe("frontend domain management", () => {
  test("super-admin can create, archive, restore, and delete a domain", async ({ page }) => {
    const domainName = uniqueDomain();

    await loginAsSuperAdmin(page);
    await page.goto("/domains");

    await page.getByRole("button", { name: "Create domain" }).click();
    await page.getByLabel("Domain name").fill(domainName);
    await page.getByLabel("Domain name").press("Enter");

    const activeRow = page.locator(".domain-row", { hasText: domainName });
    await expect(activeRow).toBeVisible();
    await expect(activeRow.getByText("active")).toBeVisible();

    await activeRow.getByRole("button", { name: "Archive" }).click();
    await page.getByLabel("Retention days").fill("30");
    await page.getByRole("button", { name: "Archive domain" }).click();

    const archivedRow = page.locator(".domain-row", { hasText: domainName });
    await expect(archivedRow.getByText("archived", { exact: true })).toBeVisible();
    await expect(archivedRow.getByText("Retention until")).toBeVisible();

    await archivedRow.getByRole("button", { name: "Pause retention" }).click();
    await expect(archivedRow.getByText("Retention paused")).toBeVisible();

    await archivedRow.getByRole("button", { name: "Resume retention" }).click();
    await expect(archivedRow.getByText("Retention paused")).toHaveCount(0);

    await archivedRow.getByRole("button", { name: "Restore" }).click();
    await expect(activeRow.getByText("active")).toBeVisible();

    await activeRow.getByRole("button", { name: "Archive" }).click();
    await page.getByRole("button", { name: "Archive domain" }).click();

    await archivedRow.getByRole("button", { name: "Delete" }).click();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "Delete archived domain" })).toBeVisible();
    await expect(page.locator(".domain-row", { hasText: domainName })).toHaveCount(1);
    await page.getByRole("button", { name: "Delete domain" }).click();

    await expect(page.locator(".domain-row", { hasText: domainName })).toHaveCount(0);
  });

  test("duplicate domain errors stay inside the create panel", async ({ page }) => {
    const domainName = uniqueDomain();

    await loginAsSuperAdmin(page);
    await page.goto("/domains");

    await page.getByRole("button", { name: "Create domain" }).click();
    await page.getByLabel("Domain name").fill(domainName);
    await page.getByLabel("Domain name").press("Enter");
    await expect(page.locator(".domain-row", { hasText: domainName })).toBeVisible();

    await page.getByRole("button", { name: "Create domain" }).click();
    await page.getByLabel("Domain name").fill(domainName);
    await page.getByLabel("Domain name").press("Enter");

    const createPanel = page.locator(".slideover-panel", { hasText: "Create domain" });
    await expect(createPanel).toBeVisible();
    await expect(createPanel.locator(".error-text")).toBeVisible();
  });
});
