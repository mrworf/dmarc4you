import { expect, test } from "@playwright/test";

import { hasSeededCredentials, loginAsRole, loginAsSuperAdmin } from "./auth";

test.describe("frontend-next cutover role matrix", () => {
  test("super-admin sees every migrated admin route", async ({ page }) => {
    await loginAsSuperAdmin(page);

    await expect(page.getByRole("link", { name: "Users" })).toBeVisible();
    await expect(page.getByRole("link", { name: "API Keys" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Audit" })).toBeVisible();

    await page.goto("/audit");
    await expect(page.getByRole("heading", { name: "Audit" })).toBeVisible();
  });

  test("admin sees admin routes but is redirected away from super-admin audit", async ({ page }) => {
    test.skip(!hasSeededCredentials("admin"), "Set DMARC_E2E_ADMIN_USERNAME and DMARC_E2E_ADMIN_PASSWORD to run admin cutover coverage.");

    await loginAsRole(page, "admin");

    await expect(page.getByRole("link", { name: "Users" })).toBeVisible();
    await expect(page.getByRole("link", { name: "API Keys" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Audit" })).toHaveCount(0);

    await page.goto("/users");
    await expect(page.getByRole("heading", { name: "Users" })).toBeVisible();

    await page.goto("/audit");
    await page.waitForURL("**/domains");
    await expect(page.getByRole("heading", { name: "Domains" })).toBeVisible();
  });

  test("manager is limited to shared operator routes", async ({ page }) => {
    test.skip(
      !hasSeededCredentials("manager"),
      "Set DMARC_E2E_MANAGER_USERNAME and DMARC_E2E_MANAGER_PASSWORD to run manager cutover coverage.",
    );

    await loginAsRole(page, "manager");

    await expect(page.getByRole("link", { name: "Domains" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Dashboards" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Search" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Upload" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Ingest Jobs" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Users" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "API Keys" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Audit" })).toHaveCount(0);

    await page.goto("/users");
    await page.waitForURL("**/domains");
    await expect(page.getByRole("heading", { name: "Domains" })).toBeVisible();
  });

  test("viewer is limited to read-oriented migrated routes", async ({ page }) => {
    test.skip(!hasSeededCredentials("viewer"), "Set DMARC_E2E_VIEWER_USERNAME and DMARC_E2E_VIEWER_PASSWORD to run viewer cutover coverage.");

    await loginAsRole(page, "viewer");

    await expect(page.getByRole("link", { name: "Domains" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Dashboards" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Search" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Upload" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Ingest Jobs" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Users" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "API Keys" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Audit" })).toHaveCount(0);

    await page.goto("/apikeys");
    await page.waitForURL("**/domains");
    await expect(page.getByRole("heading", { name: "Domains" })).toBeVisible();
  });
});
