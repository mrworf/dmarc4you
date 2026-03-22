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

async function openDashboardFilters(page: Page): Promise<Locator> {
  await page.getByRole("button", { name: "Filters" }).click();
  const filtersPanel = page.locator('[role="dialog"]').filter({ has: page.getByRole("heading", { name: "Filters" }) });
  await expect(filtersPanel).toBeVisible();
  return filtersPanel;
}

function expectBoundingBox(value: Box | null, label: string): Box {
  expect(value, `${label} should have a bounding box`).not.toBeNull();
  return value as Box;
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
    await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();
    await expect(page.getByLabel("Search", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Edit dashboard" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Export YAML" })).toBeVisible();
  });

  test("dashboard detail updates filters without reloading and keeps state in the URL", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    const overviewSection = page.locator("section.surface-card").filter({ has: page.getByLabel("Search", { exact: true }) });
    await expect(overviewSection).toBeVisible();
    const marker = await installNoReloadMarker(page);
    await overviewSection.getByLabel("Search", { exact: true }).fill("192.0.2.21");
    await expect(page).toHaveURL(/query=192\.0\.2\.21/);
    await expectNoReload(page, marker);
    await expect(page.getByText("Search: 192.0.2.21")).toBeVisible();
    const resultsSection = page.locator("section.surface-card").filter({ has: page.getByRole("heading", { name: "Results" }) });
    await expect(resultsSection.locator(".results-header-copy").getByText("Search: 192.0.2.21")).toBeVisible();

    await page.reload();

    await expect(overviewSection.getByLabel("Search", { exact: true })).toHaveValue("192.0.2.21");
    await expect(page.getByText("Search: 192.0.2.21")).toBeVisible();
  });

  test("dashboard detail moves controls into results and removes the old summary cards", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    const hero = page.locator("header.page-hero");
    const overviewSection = page.locator("section.surface-card").filter({ has: page.getByLabel("Search", { exact: true }) });
    await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();
    await expect(page.locator(".stat-card")).toHaveCount(0);
    await expect(page.getByText(/Dashboard period:/)).toHaveCount(0);
    await expect(page.getByText("Review live results, update dashboard settings, and manage access for this view.")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Overview" })).toHaveCount(0);
    await expect(page.getByText("The essentials for this saved dashboard.")).toHaveCount(0);
    await expect(overviewSection.getByLabel("Search", { exact: true })).toBeVisible();
    await expect(overviewSection.locator(".field-label-inline")).toBeVisible();

    const titleBox = expectBoundingBox(await hero.locator(".page-title-text").boundingBox(), "dashboard title");
    const descriptionBox = expectBoundingBox(await hero.locator(".page-title-detail").boundingBox(), "dashboard description");
    const actionsBox = expectBoundingBox(await hero.locator(".dashboard-hero-actions").boundingBox(), "dashboard actions");
    expect(Math.abs(descriptionBox.y - titleBox.y)).toBeLessThan(24);
    expect(actionsBox.y).toBeGreaterThan(titleBox.y + titleBox.height - 2);

    const searchLabelBox = expectBoundingBox(await overviewSection.locator(".field-label-inline > span").boundingBox(), "search label");
    const searchInputBox = expectBoundingBox(await overviewSection.getByLabel("Search", { exact: true }).boundingBox(), "search input");
    expect(Math.abs(searchLabelBox.y - searchInputBox.y)).toBeLessThan(16);
    expect(searchInputBox.x).toBeGreaterThan(searchLabelBox.x + searchLabelBox.width);

    const resultsSection = page.locator("section.surface-card").filter({ has: page.getByRole("heading", { name: "Results" }) });
    await expect(resultsSection.getByRole("button", { name: "Range" })).toBeVisible();
    await expect(resultsSection.getByLabel("Range start")).toBeVisible();
    await expect(resultsSection.getByLabel("Range end")).toBeVisible();
    await expect(resultsSection.getByRole("button", { name: "Filters" })).toBeVisible();
    await expect(resultsSection.locator(".pagination-controls").getByLabel("Records")).toBeVisible();

    const rangeButtonBox = expectBoundingBox(await resultsSection.getByRole("button", { name: "Range" }).boundingBox(), "range button");
    const rangeStartBox = expectBoundingBox(await resultsSection.getByLabel("Range start").boundingBox(), "range start");
    const filtersButtonBox = expectBoundingBox(await resultsSection.getByRole("button", { name: "Filters" }).boundingBox(), "filters button");
    expect(Math.abs(rangeButtonBox.y - rangeStartBox.y)).toBeLessThan(16);
    expect(Math.abs(filtersButtonBox.y - rangeStartBox.y)).toBeLessThan(16);
    await expect(resultsSection.locator(".results-header-controls")).toBeVisible();

    const filtersPanel = await openDashboardFilters(page);
    await expect(filtersPanel.getByText("Country", { exact: true })).toBeVisible();
    await expect(filtersPanel.getByText("Grouping", { exact: true })).toBeVisible();
    await expect(filtersPanel.getByLabel("Add grouping")).toBeVisible();
  });

  test("dashboard detail grouping updates immediately across multiple levels", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();
    const marker = await installNoReloadMarker(page);
    const filtersPanel = await openDashboardFilters(page);

    await filtersPanel.getByRole("button", { name: "Add level" }).click();
    await expect(page).toHaveURL(/grouping=domain/);
    await expectNoReload(page, marker);

    await filtersPanel.getByLabel("Add grouping").selectOption("disposition");
    await filtersPanel.getByRole("button", { name: "Add level" }).click();
    await expect(page).toHaveURL(/grouping=domain(?:%2C|,)disposition/);
    await expectNoReload(page, marker);

    await filtersPanel.getByRole("button", { name: "Move Domain later" }).click();
    await expect(page).toHaveURL(/grouping=disposition(?:%2C|,)domain/);
    await expectNoReload(page, marker);

    await filtersPanel.getByRole("button", { name: "Remove Disposition" }).click();
    await expect(page).toHaveURL(/grouping=domain/);
    await expectNoReload(page, marker);
  });

  test("dashboard detail keeps grouped branches open during live filter refresh", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();
    const marker = await installNoReloadMarker(page);
    const filtersPanel = await openDashboardFilters(page);

    await filtersPanel.getByLabel("Add grouping").selectOption("source_ip");
    await filtersPanel.getByRole("button", { name: "Add level" }).click();

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

    await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();
    const marker = await installNoReloadMarker(page);
    const filtersPanel = await openDashboardFilters(page);

    await filtersPanel.getByRole("button", { name: "Add level" }).click();
    await filtersPanel.getByLabel("Add grouping").selectOption("disposition");
    await filtersPanel.getByRole("button", { name: "Add level" }).click();

    const firstToggle = page.locator(".group-toggle").first();
    await expect(firstToggle).toBeVisible();
    await firstToggle.click();
    await expect(firstToggle).toHaveAttribute("aria-expanded", "true");

    await filtersPanel.getByRole("button", { name: "Remove Disposition" }).click();

    await expectNoReload(page, marker);
    await expect(firstToggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.locator(".group-leaf-wrap").first()).toBeVisible();
  });

  test("dashboard detail keeps multi-word added search terms intact and removable", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();

    const overviewSection = page.locator("section.surface-card").filter({ has: page.getByLabel("Search", { exact: true }) });
    await overviewSection.getByLabel("Search", { exact: true }).fill("192.0.2.21");
    const orgButton = page.getByRole("button", { name: "Google Workspace", exact: true }).first();
    await expect(orgButton).toBeVisible();
    await orgButton.click();

    await expect(overviewSection.getByLabel("Search", { exact: true })).toHaveValue('192.0.2.21 "Google Workspace"');
    await expect(page.getByText("Search: 192.0.2.21")).toBeVisible();
    await expect(page.getByText("Search: Google Workspace")).toBeVisible();
    await expect(page).toHaveURL(/query=192\.0\.2\.21(?:\+|%20)%22Google(?:\+|%20)Workspace%22/);

    await page.getByRole("button", { name: "Remove Search: Google Workspace" }).click();

    await expect(overviewSection.getByLabel("Search", { exact: true })).toHaveValue("192.0.2.21");
    await expect(page.getByText("Search: Google Workspace")).toHaveCount(0);
    await expect(page.getByText("Search: 192.0.2.21")).toBeVisible();
    await expect(page).toHaveURL(/query=192\.0\.2\.21/);
  });

  test("dashboard grouped view hides redundant bar counts without showing a dashboard period banner", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();

    const fromValue = process.env.DMARC_E2E_SEARCH_FROM ?? "2025-01-01";
    const toValue = process.env.DMARC_E2E_SEARCH_TO ?? "2025-12-31";
    await page.getByLabel("Range start").fill(fromValue);
    await page.getByLabel("Range end").fill(toValue);
    const filtersPanel = await openDashboardFilters(page);
    await filtersPanel.getByRole("button", { name: "Add level" }).click();

    await expect(page.locator(".grouped-data-table")).toBeVisible();
    await expect(page.getByText(/Dashboard period:/)).toHaveCount(0);
    await expect(page.locator(".grouped-data-table thead").getByText("Period")).toHaveCount(0);
    await expect(page.locator(".grouped-data-table .summary-bar-count")).toHaveCount(0);
  });

  test("dashboard range presets prefill the date inputs without reloading", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    const marker = await installNoReloadMarker(page);
    await page.getByRole("button", { name: "Range" }).click();
    await page.getByRole("menuitem", { name: "Last 30 days" }).click();

    await expect(page.getByLabel("Range start")).not.toHaveValue("");
    await expect(page.getByLabel("Range end")).not.toHaveValue("");
    await expect(page).toHaveURL(/from=\d{4}-\d{2}-\d{2}/);
    await expect(page).toHaveURL(/to=\d{4}-\d{2}-\d{2}/);
    await expectNoReload(page, marker);

    await page.getByRole("button", { name: "Range" }).click();
    await page.getByRole("menuitem", { name: "Show All" }).click();
    await expect(page.getByLabel("Range start")).toHaveValue("");
    await expect(page.getByLabel("Range end")).toHaveValue("");
    await expect(page).not.toHaveURL(/(?:\?|&)from=/);
    await expect(page).not.toHaveURL(/(?:\?|&)to=/);
  });

  test("dashboard detail hover menu supports include, exclude, and group actions", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await openAnyDashboardDetail(page);

    const firstDispositionButton = page
      .locator(".data-table tbody tr .cell-primary-action")
      .filter({ has: page.locator(".status-pill-disposition-none, .status-pill-disposition-quarantine, .status-pill-disposition-reject") })
      .first();
    await expect(firstDispositionButton).toBeVisible();
    const dispositionText = (await firstDispositionButton.textContent())?.trim() ?? "";

    await firstDispositionButton.click();
    await expect(page.getByText(`Disposition: ${dispositionText}`)).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`include_disposition=${dispositionText.toLowerCase()}`));
    await page.getByRole("button", { name: `Remove Disposition: ${dispositionText}` }).click();

    await firstDispositionButton.hover();
    const hoverMenu = page.getByRole("menu", { name: `${dispositionText} actions` });
    const excludeAction = hoverMenu.getByRole("menuitem", { name: "Exclude" });
    await expect(excludeAction).toBeVisible();
    await excludeAction.click();
    await expect(page.getByText(`Not disposition: ${dispositionText}`)).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`exclude_disposition=${dispositionText.toLowerCase()}`));
    await page.getByRole("button", { name: `Remove Not disposition: ${dispositionText}` }).click();

    await firstDispositionButton.hover();
    const groupAction = hoverMenu.getByRole("menuitem", { name: "Group" });
    await expect(groupAction).toBeVisible();
    await groupAction.click();
    await expect(page).toHaveURL(/grouping=disposition/);
    await expect(page.locator(".grouped-data-table")).toBeVisible();
    await expect(page.locator(".cell-exclude-trigger")).toHaveCount(0);
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

    await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();

    await page.setViewportSize({ width: 1440, height: 1100 });
    const standardWidth = await page.locator("main.app-frame-app").evaluate((element) => element.getBoundingClientRect().width);

    await page.setViewportSize({ width: 2200, height: 1100 });
    await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();
    const wideWidth = await page.locator("main.app-frame-app").evaluate((element) => element.getBoundingClientRect().width);

    expect(wideWidth).toBeGreaterThan(standardWidth + 500);
    expect(wideWidth).toBeGreaterThan(2000);
  });

  test("aggregate search keeps its existing range labels and does not use dashboard overview search placement", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/search");

    await expect(page.getByRole("heading", { name: "Search", exact: true })).toBeVisible();
    await expect(page.getByLabel("From", { exact: true })).toBeVisible();
    await expect(page.getByLabel("To", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Range" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Overview" })).toHaveCount(0);
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
type Box = {
  x: number;
  y: number;
  width: number;
  height: number;
};
