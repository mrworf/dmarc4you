import { expect, test, type Page } from "@playwright/test";

import { loginAsSuperAdmin } from "./auth";

function buildSearchUrl(params: Record<string, string>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) {
      search.set(key, value);
    }
  }
  const query = search.toString();
  return query ? `/search?${query}` : "/search";
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

async function applyDefaultAggregateFilters(page: Page) {
  const configuredDomain = process.env.DMARC_E2E_SEARCH_DOMAIN;

  await page.getByLabel("Free-text search").fill(process.env.DMARC_E2E_SEARCH_QUERY ?? "google");

  if (configuredDomain) {
    await page.getByLabel(configuredDomain, { exact: true }).check();
  } else {
    const firstDomainCheckbox = page.locator(".search-domain-grid input[type='checkbox']").first();
    await expect(firstDomainCheckbox).toBeVisible();
    await firstDomainCheckbox.check();
  }

  await page.getByRole("button", { name: "More filters" }).click();
  const filtersPanel = page.locator('[role="dialog"]').filter({ has: page.getByRole("heading", { name: "More filters" }) });
  await filtersPanel.locator(".stack").nth(0).locator(".checkbox-card").filter({ hasText: "Pass" }).click();
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page).toHaveURL(/include_spf=pass/);
}

test.describe("frontend-next search coverage", () => {
  test("aggregate search updates filters without reloading and restores state from query params", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/search");

    await expect(page.getByRole("heading", { name: "Search", exact: true })).toBeVisible();
    await expect(page.getByText("Nothing is loaded yet.")).toBeVisible();
    const marker = await installNoReloadMarker(page);
    await page.getByLabel(process.env.DMARC_E2E_SEARCH_DOMAIN ?? "example.com", { exact: true }).check();
    await page.getByLabel("Free-text search").fill(process.env.DMARC_E2E_SEARCH_QUERY ?? "google");

    await expect(page).toHaveURL(/\/search\?/);
    await expect(page).toHaveURL(/domains=example\.com/);
    await expect(page).toHaveURL(/query=google/);
    await expectNoReload(page, marker);
    await expect(page.getByLabel("Free-text search")).toHaveValue(process.env.DMARC_E2E_SEARCH_QUERY ?? "google");
    await expect(page.getByText(`Search: ${process.env.DMARC_E2E_SEARCH_QUERY ?? "google"}`)).toBeVisible();
    await expect(page.getByText("Domain: example.com")).toBeVisible();

    await page.reload();

    await expect(page.getByRole("heading", { name: "Search", exact: true })).toBeVisible();
    await expect(page.getByLabel("Free-text search")).toHaveValue(process.env.DMARC_E2E_SEARCH_QUERY ?? "google");
    await expect(page.getByText("Domain: example.com")).toBeVisible();

    if (process.env.DMARC_E2E_SEARCH_DOMAIN) {
      await expect(page.getByLabel(process.env.DMARC_E2E_SEARCH_DOMAIN, { exact: true })).toBeChecked();
    } else {
      await expect(page.locator(".search-domain-grid input[type='checkbox']").first()).toBeChecked();
    }
  });

  test("aggregate search grouping supports multiple live levels", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/search");

    await expect(page.getByRole("heading", { name: "Search", exact: true })).toBeVisible();
    const marker = await installNoReloadMarker(page);

    const configuredDomain = process.env.DMARC_E2E_SEARCH_DOMAIN;
    if (configuredDomain) {
      await page.getByLabel(configuredDomain, { exact: true }).check();
    } else {
      await page.locator(".search-domain-grid input[type='checkbox']").first().check();
    }

    await page.getByRole("button", { name: "Add level" }).click();
    await expect(page).toHaveURL(/grouping=domain/);
    await expectNoReload(page, marker);

    await page.getByLabel("Add grouping").selectOption("disposition");
    await page.getByRole("button", { name: "Add level" }).click();
    await expect(page).toHaveURL(/grouping=domain(?:%2C|,)disposition/);
    await expectNoReload(page, marker);
  });

  test("aggregate search debounces text/date changes and persists them after reload", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/search");

    await expect(page.getByRole("heading", { name: "Search", exact: true })).toBeVisible();
    const marker = await installNoReloadMarker(page);

    const configuredDomain = process.env.DMARC_E2E_SEARCH_DOMAIN;
    if (configuredDomain) {
      await page.getByLabel(configuredDomain, { exact: true }).check();
    } else {
      await page.locator(".search-domain-grid input[type='checkbox']").first().check();
    }

    await page.getByLabel("Free-text search").fill(process.env.DMARC_E2E_SEARCH_QUERY ?? "google");
    await page.getByLabel("From", { exact: true }).fill(process.env.DMARC_E2E_SEARCH_FROM ?? "2025-01-01");
    await page.getByLabel("To", { exact: true }).fill(process.env.DMARC_E2E_SEARCH_TO ?? "2025-01-31");

    await expect(page).toHaveURL(/query=/);
    await expect(page).toHaveURL(/from=/);
    await expect(page).toHaveURL(/to=/);
    await expectNoReload(page, marker);

    await page.reload();

    await expect(page.getByLabel("Free-text search")).toHaveValue(process.env.DMARC_E2E_SEARCH_QUERY ?? "google");
    await expect(page.getByLabel("From", { exact: true })).toHaveValue(process.env.DMARC_E2E_SEARCH_FROM ?? "2025-01-01");
    await expect(page.getByLabel("To", { exact: true })).toHaveValue(process.env.DMARC_E2E_SEARCH_TO ?? "2025-01-31");
  });

  test("search route switches between aggregate and forensic modes", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/search");

    await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();
    await page.getByLabel("Report type").selectOption("forensic");
    await page.getByRole("button", { name: "Search" }).click();

    await expect(page).toHaveURL(/report_type=forensic/);
    await expect(page.getByRole("heading", { name: "Forensic reports" })).toBeVisible();
    await expect(page.getByLabel("Free-text search")).toBeDisabled();
    await expect(page.getByText("Forensic reports require a domain or date filter before loading.")).toBeVisible();

    await page.reload();

    await expect(page.getByLabel("Report type")).toHaveValue("forensic");
    await expect(page.getByRole("heading", { name: "Forensic reports" })).toBeVisible();
  });

  test("search pagination keeps page state in the URL", async ({ page }) => {
    await loginAsSuperAdmin(page);

    await page.goto(
      buildSearchUrl({
        domains: process.env.DMARC_E2E_SEARCH_DOMAIN ?? "",
        query: process.env.DMARC_E2E_SEARCH_QUERY ?? "",
        from: process.env.DMARC_E2E_SEARCH_FROM ?? "",
        to: process.env.DMARC_E2E_SEARCH_TO ?? "",
      }),
    );

    await expect(page.getByRole("heading", { name: "Search", exact: true })).toBeVisible();
    const paginationSummary = page.locator(".pagination-row .status-text");
    await expect(paginationSummary).toBeVisible();

    const summaryText = (await paginationSummary.textContent()) ?? "";
    const match = summaryText.match(/Page\s+(\d+)\s+of\s+(\d+)/);
    const totalPages = match ? Number.parseInt(match[2], 10) : 1;

    test.skip(
      totalPages < 2,
      "Pagination coverage needs seeded search data that returns more than one page for the selected filters.",
    );

    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(page).toHaveURL(/page=2/);
    await expect(paginationSummary).toContainText("Page 2 of");

    await page.reload();

    await expect(page).toHaveURL(/page=2/);
    await expect(paginationSummary).toContainText("Page 2 of");
  });

  test("search chips can be removed after applying filters", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/search");

    await applyDefaultAggregateFilters(page);
    await expect(page.getByText("SPF: Pass")).toBeVisible();

    const spfChip = page.locator(".filter-chip", { hasText: "SPF: Pass" });
    await spfChip.getByRole("button").click();

    await expect(page.getByText("SPF: Pass")).toHaveCount(0);
    await expect(page).not.toHaveURL(/include_spf=pass/);
  });

  test("aggregate result quick filters update the active search", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/search");

    await applyDefaultAggregateFilters(page);

    const firstQuickFilter = page.locator(".cell-primary-action").first();
    test.skip((await firstQuickFilter.count()) === 0, "Quick-filter coverage needs seeded aggregate search results.");

    const chipCountBefore = await page.locator(".filter-chip").count();
    const urlBefore = page.url();
    await firstQuickFilter.click();

    await expect(page).toHaveURL(/search\?/);
    expect(page.url()).not.toBe(urlBefore);
    const chipCountAfter = await page.locator(".filter-chip").count();
    expect(chipCountAfter).toBeGreaterThanOrEqual(chipCountBefore);
  });
});
