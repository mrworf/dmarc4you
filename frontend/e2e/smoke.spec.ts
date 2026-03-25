import { expect, test } from "@playwright/test";

import { loginAsSuperAdmin } from "./auth";

test.describe("frontend smoke", () => {
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
    await expect(page.getByRole("heading", { name: "Trend" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();
  });

  test("super-admin audit route renders with query-param filters", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/audit?action_type=login_success&page=1");

    await expect(page.getByRole("heading", { name: "Audit", exact: true })).toBeVisible();
    await expect(page.locator(".field-label").filter({ hasText: "Action types" })).toBeVisible();
    await expect(page.locator(".filter-chip")).toContainText(["login_success"]);
    await expect(page.getByRole("heading", { name: "Audit log" })).toBeVisible();
  });

  test("domain monitoring detail route renders from the domains list", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/domains");

    const detailLink = page.getByRole("link", { name: "View details" }).first();
    await expect(detailLink).toBeVisible();
    await detailLink.click();

    await page.waitForURL(/\/domains\/[^/?#]+$/);
    await expect(page.getByRole("heading", { name: "Current DNS state" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Change history" })).toBeVisible();
  });

  test("domain monitoring timeline route renders from the detail page", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/domains");

    const detailLink = page.getByRole("link", { name: "View details" }).first();
    await expect(detailLink).toBeVisible();
    await detailLink.click();

    await page.waitForURL(/\/domains\/[^/?#]+$/);
    await page.getByRole("link", { name: "View timeline" }).click();

    await page.waitForURL(/\/domains\/[^/?#]+\/monitoring\/timeline$/);
    await expect(page.getByRole("heading", { name: "Freshness" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Timeline", exact: true })).toBeVisible();
  });

  test("domain maintenance job detail route renders after recompute is queued", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/domains");

    const recomputeButton = page.getByRole("button", { name: "Recompute reports" }).first();
    await expect(recomputeButton).toBeVisible();
    await recomputeButton.click();

    await expect(page.getByRole("heading", { name: "Recompute aggregate reports" })).toBeVisible();
    await page.getByRole("button", { name: "Recompute reports" }).last().click();

    const jobLink = page.getByRole("link", { name: "View maintenance job" }).first();
    await expect(jobLink).toBeVisible();
    await jobLink.click();

    await page.waitForURL(/\/domain-maintenance-jobs\/[^/?#]+$/);
    await expect(page.getByRole("heading", { name: /Maintenance job / })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Job detail" })).toBeVisible();
  });
});
