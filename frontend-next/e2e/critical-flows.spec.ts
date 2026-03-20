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

async function getVisibleColumnOrder(page: Page): Promise<string[]> {
  return page.locator(".slideover-panel [data-column-value]").evaluateAll((elements) =>
    elements.map((element) => element.getAttribute("data-column-value") ?? ""),
  );
}

async function expectJobLink(page: Page): Promise<Locator> {
  const jobLink = page.locator('a[href^="/ingest-jobs/"]').first();
  await expect(jobLink).toBeVisible();
  return jobLink;
}

async function installNoReloadMarker(page: Page): Promise<string> {
  return page.evaluate(() => {
    const marker = `marker-${Math.random().toString(36).slice(2, 12)}`;
    (window as Window & { __pwNoReloadMarker?: string }).__pwNoReloadMarker = marker;
    return marker;
  });
}

async function expectNoReload(page: Page, marker: string): Promise<void> {
  await expect
    .poll(() =>
      page.evaluate(() => (window as Window & { __pwNoReloadMarker?: string }).__pwNoReloadMarker ?? ""),
    )
    .toBe(marker);
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

  test("dashboard detail updates filters without reloading and keeps state in the URL", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    const marker = await installNoReloadMarker(page);
    await page.getByLabel("Search", { exact: true }).fill("192.0.2.21");
    await expect(page).toHaveURL(/query=192\.0\.2\.21/);
    await expectNoReload(page, marker);
    await expect(page.getByText("Search: 192.0.2.21")).toBeVisible();

    await page.reload();

    await expect(page.getByLabel("Search", { exact: true })).toHaveValue("192.0.2.21");
    await expect(page.getByText("Search: 192.0.2.21")).toBeVisible();
  });

  test("dashboard detail grouping updates immediately across multiple levels", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    const marker = await installNoReloadMarker(page);

    await page.getByRole("button", { name: "Add level" }).click();
    await expect(page).toHaveURL(/grouping=domain/);
    await expectNoReload(page, marker);

    await page.getByLabel("Add grouping").selectOption("disposition");
    await page.getByRole("button", { name: "Add level" }).click();
    await expect(page).toHaveURL(/grouping=domain(?:%2C|,)disposition/);
    await expectNoReload(page, marker);

    await page.getByRole("button", { name: "Move Domain later" }).click();
    await expect(page).toHaveURL(/grouping=disposition(?:%2C|,)domain/);
    await expectNoReload(page, marker);

    await page.getByRole("button", { name: "Remove Disposition" }).click();
    await expect(page).toHaveURL(/grouping=domain/);
    await expectNoReload(page, marker);
  });

  test("dashboard detail keeps grouped branches open during live filter refresh", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    const marker = await installNoReloadMarker(page);

    await page.getByLabel("Add grouping").selectOption("source_ip");
    await page.getByRole("button", { name: "Add level" }).click();

    const firstToggle = page.locator(".group-toggle").first();
    await expect(firstToggle).toBeVisible();
    await firstToggle.click();
    await expect(firstToggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.locator(".group-leaf-wrap").first()).toBeVisible();

    const firstGroupQuickFilter = page.locator(".group-row .cell-primary-action").first();

    await firstGroupQuickFilter.click();

    await expectNoReload(page, marker);
    await expect(firstToggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.locator(".group-leaf-wrap").first()).toBeVisible();
  });

  test("dashboard detail keeps compatible grouped branches open when removing deeper grouping", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    const marker = await installNoReloadMarker(page);

    await page.getByRole("button", { name: "Add level" }).click();
    await page.getByLabel("Add grouping").selectOption("disposition");
    await page.getByRole("button", { name: "Add level" }).click();

    const firstToggle = page.locator(".group-toggle").first();
    await expect(firstToggle).toBeVisible();
    await firstToggle.click();
    await expect(firstToggle).toHaveAttribute("aria-expanded", "true");

    await page.getByRole("button", { name: "Remove Disposition" }).click();

    await expectNoReload(page, marker);
    await expect(firstToggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.locator(".group-leaf-wrap").first()).toBeVisible();
  });

  test("dashboard detail keeps multi-word added search terms intact and removable", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

    await page.getByLabel("Search", { exact: true }).fill("192.0.2.21");
    const orgButton = page.getByRole("button", { name: "Google Workspace", exact: true }).first();
    await expect(orgButton).toBeVisible();
    await orgButton.click();

    await expect(page.getByLabel("Search", { exact: true })).toHaveValue('192.0.2.21 "Google Workspace"');
    await expect(page.getByText("Search: 192.0.2.21")).toBeVisible();
    await expect(page.getByText("Search: Google Workspace")).toBeVisible();
    await expect(page).toHaveURL(/query=192\.0\.2\.21(?:\+|%20)%22Google(?:\+|%20)Workspace%22/);

    await page.getByRole("button", { name: "Remove Search: Google Workspace" }).click();

    await expect(page.getByLabel("Search", { exact: true })).toHaveValue("192.0.2.21");
    await expect(page.getByText("Search: Google Workspace")).toHaveCount(0);
    await expect(page.getByText("Search: 192.0.2.21")).toBeVisible();
    await expect(page).toHaveURL(/query=192\.0\.2\.21/);
  });

  test("dashboard grouped view hides redundant bar counts and shows one dashboard-wide period summary", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

    const fromValue = process.env.DMARC_E2E_SEARCH_FROM ?? "2025-01-01";
    const toValue = process.env.DMARC_E2E_SEARCH_TO ?? "2025-12-31";
    await page.getByLabel("From", { exact: true }).fill(fromValue);
    await page.getByLabel("To", { exact: true }).fill(toValue);
    await page.getByRole("button", { name: "Add level" }).click();

    await expect(page.locator(".grouped-data-table")).toBeVisible();
    await expect(page.getByText(`Dashboard period: From ${fromValue} to ${toValue}`)).toBeVisible();
    await expect(page.locator(".grouped-data-table thead").getByText("Period")).toHaveCount(0);
    await expect(page.locator(".grouped-data-table .summary-bar-count")).toHaveCount(0);
  });

  test("dashboard detail edit supports live drag reordering and persists visible columns", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    await page.getByRole("button", { name: "Edit dashboard" }).click();
    await expect(page.getByRole("heading", { name: "Edit dashboard" })).toBeVisible();

    const initialOrder = await getVisibleColumnOrder(page);
    expect(initialOrder.length).toBeGreaterThan(2);

    const draggedColumn = initialOrder[0];
    const hoverTarget = initialOrder[2];
    const dragHandle = page.locator(`[data-column-value="${draggedColumn}"] .drag-handle`);
    const targetRow = page.locator(`[data-column-value="${hoverTarget}"]`);
    const dataTransfer = await page.evaluateHandle(() => new DataTransfer());

    await dragHandle.dispatchEvent("dragstart", { dataTransfer });
    await targetRow.dispatchEvent("dragenter", { dataTransfer });
    await targetRow.dispatchEvent("dragover", { dataTransfer });

    const reorderedBeforeDrop = await getVisibleColumnOrder(page);
    expect(reorderedBeforeDrop.indexOf(draggedColumn)).toBe(2);

    await targetRow.dispatchEvent("drop", { dataTransfer });
    await dragHandle.dispatchEvent("dragend", { dataTransfer });

    const reorderedAfterDrop = await getVisibleColumnOrder(page);
    expect(reorderedAfterDrop.indexOf(draggedColumn)).toBe(2);

    const movedColumn = reorderedAfterDrop[0];
    await page.locator(`[data-column-value="${movedColumn}"]`).getByRole("button", { name: "Move down" }).click();

    const afterMoveButton = await getVisibleColumnOrder(page);
    expect(afterMoveButton.indexOf(movedColumn)).toBe(1);

    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByRole("heading", { name: "Edit dashboard" })).toHaveCount(0);

    await page.getByRole("button", { name: "Edit dashboard" }).click();
    await expect(page.getByRole("heading", { name: "Edit dashboard" })).toBeVisible();
    await expect.poll(() => getVisibleColumnOrder(page)).toEqual(afterMoveButton);
  });

  test("authenticated shell expands on ultrawide resize", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

    await page.setViewportSize({ width: 1440, height: 1100 });
    const standardWidth = await page.locator("main.app-frame-app").evaluate((element) => element.getBoundingClientRect().width);

    await page.setViewportSize({ width: 2200, height: 1100 });
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    const wideWidth = await page.locator("main.app-frame-app").evaluate((element) => element.getBoundingClientRect().width);

    expect(wideWidth).toBeGreaterThan(standardWidth + 500);
    expect(wideWidth).toBeGreaterThan(2000);
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
