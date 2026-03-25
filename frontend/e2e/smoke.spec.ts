import { expect, test } from "@playwright/test";

import { loginAsSuperAdmin } from "./auth";

test.describe("frontend-next smoke", () => {
  test("anonymous route guard redirects to login", async ({ page }) => {
    await page.goto("/domains");

    await page.waitForURL("**/login");
    await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  });

  test("login renders the migrated domains page", async ({ page }) => {
    await loginAsSuperAdmin(page);

    await expect(page.getByRole("heading", { name: "Domains", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Domain inventory" })).toBeVisible();
  });

  test("dashboards landing route renders after login", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/dashboards");

    await expect(page.getByRole("heading", { name: "Dashboards", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Your dashboards" })).toBeVisible();
  });

  test("dashboard detail route renders from seeded data", async ({ page }) => {
    await loginAsSuperAdmin(page);

    const seededDashboardId = process.env.DMARC_E2E_DASHBOARD_ID;
    if (seededDashboardId) {
      await page.goto(`/dashboards/${seededDashboardId}`);
    } else {
      await page.goto("/dashboards");
      const detailLink = page.locator('a[href^="/dashboards/"]').first();
      await expect(detailLink).toBeVisible();
      await detailLink.click();
    }

    await page.waitForURL(/\/dashboards\/[^/?#]+/);
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  });

  test("super-admin audit route renders with query-param filters", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/audit?action_type=login_success&page=1");

    await expect(page.getByRole("heading", { name: "Audit", exact: true })).toBeVisible();
    await expect(page.getByLabel("Action type")).toHaveValue("login_success");
    await expect(page.getByRole("heading", { name: "Audit log" })).toBeVisible();
  });
});
