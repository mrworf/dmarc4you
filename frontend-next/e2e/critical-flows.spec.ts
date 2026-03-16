import { expect, test, type Locator, type Page } from "@playwright/test";

import { loginAsSuperAdmin } from "./auth";

const MINIMAL_AGGREGATE_XML = `<?xml version="1.0" encoding="UTF-8"?>
<feedback xmlns="urn:ietf:params:xml:ns:dmarc-1">
  <report_metadata>
    <org_name>Playwright Org</org_name>
    <report_id>playwright-contract-20260315</report_id>
    <date_range>
      <begin>1741996800</begin>
      <end>1742083200</end>
    </date_range>
  </report_metadata>
  <policy_published>
    <domain>example.com</domain>
  </policy_published>
</feedback>`;

function uniqueSuffix(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

async function selectFirstDomainOption(page: Page): Promise<void> {
  const firstDomainCheckbox = page.locator("input[type='checkbox']").first();
  await expect(firstDomainCheckbox).toBeVisible();
  await firstDomainCheckbox.check();
}

async function openAnyDashboardDetail(page: Page): Promise<void> {
  const seededDashboardId = process.env.DMARC_E2E_DASHBOARD_ID;
  if (seededDashboardId) {
    await page.goto(`/dashboards/${seededDashboardId}`);
    return;
  }

  await page.goto("/dashboards");
  const firstDetailLink = page.locator('a[href^="/dashboards/"]').first();
  await expect(firstDetailLink).toBeVisible();
  await firstDetailLink.click();
}

async function expectJobLink(page: Page): Promise<Locator> {
  const jobLink = page.locator('a[href^="/ingest-jobs/"]').first();
  await expect(jobLink).toBeVisible();
  return jobLink;
}

test.describe("frontend-next critical happy paths", () => {
  test("dashboards route creates a dashboard and exposes detail actions", async ({ page }) => {
    const dashboardName = `pw-dashboard-${uniqueSuffix()}`;

    await loginAsSuperAdmin(page);
    await page.goto("/dashboards");

    await expect(page.getByRole("heading", { name: "Dashboards", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Create dashboard" }).first().click();
    await page.getByLabel("Name").fill(dashboardName);
    await page.getByLabel("Description").fill("Created by Playwright critical-flow coverage.");
    await selectFirstDomainOption(page);
    await page.getByRole("button", { name: "Create dashboard" }).last().click();

    const createdLink = page.getByRole("link", { name: dashboardName });
    await expect(createdLink).toBeVisible();
    await createdLink.click();

    await page.waitForURL(/\/dashboards\/[^/?#]+/);
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Edit dashboard" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Export YAML" })).toBeVisible();
  });

  test("dashboard detail keeps filter state in the URL", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    await page.getByLabel("Include SPF").selectOption("pass");
    await page.getByRole("button", { name: "Apply filters" }).click();

    await expect(page).toHaveURL(/include_spf=pass/);
    await page.reload();

    await expect(page.getByLabel("Include SPF")).toHaveValue("pass");
  });

  test("upload route submits XML and links to the ingest job detail", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/upload");

    await expect(page.getByRole("heading", { name: "Upload", exact: true })).toBeVisible();
    await page.getByLabel("Paste XML").fill(MINIMAL_AGGREGATE_XML);
    await page.getByRole("button", { name: "Submit upload" }).click();

    await expect(page.getByText("Upload submitted as one ingest job.")).toBeVisible();
    const jobLink = await expectJobLink(page);
    await jobLink.click();

    await page.waitForURL(/\/ingest-jobs\/[^/?#]+/);
    await expect(page.getByRole("heading", { name: "Job detail" })).toBeVisible();
  });

  test("users route creates a local account and shows the one-time password", async ({ page }) => {
    const suffix = uniqueSuffix();
    const username = `pwviewer-${suffix}`;

    await loginAsSuperAdmin(page);
    await page.goto("/users");

    await expect(page.getByRole("heading", { name: "Users" })).toBeVisible();
    await page.getByRole("button", { name: "Create user" }).first().click();
    await page.getByLabel("Username").fill(username);
    await page.getByLabel("Role").selectOption("viewer");
    await page.getByLabel("Full name").fill(`Playwright Viewer ${suffix}`);
    await page.getByLabel("Email").fill(`playwright-${suffix}@example.com`);
    await page.getByLabel("Email").press("Enter");

    await expect(page.getByText("User created")).toBeVisible();
    await expect(page.getByText("Temporary password")).toBeVisible();
  });

  test("api keys route creates a key and shows the copy-once secret", async ({ page }) => {
    const nickname = `pw-key-${uniqueSuffix()}`;

    await loginAsSuperAdmin(page);
    await page.goto("/apikeys");

    await expect(page.getByRole("heading", { name: "API Keys" })).toBeVisible();
    await page.getByRole("button", { name: "Create API key" }).first().click();
    await page.getByLabel("Nickname").fill(nickname);
    await page.getByLabel("Description").fill("Created by Playwright critical-flow coverage.");
    await selectFirstDomainOption(page);
    await page.getByLabel("Description").press("Enter");

    await expect(page.getByText("API key created")).toBeVisible();
    await expect(page.getByText("Raw secret")).toBeVisible();
  });
});
