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

async function applyDefaultAggregateFilters(page: Page) {
  const configuredDomain = process.env.DMARC_E2E_SEARCH_DOMAIN;

  await page.getByLabel("Free-text search").fill(process.env.DMARC_E2E_SEARCH_QUERY ?? "google");
  await page.getByRole("button", { name: "More filters" }).click();
  const filtersPanel = page.locator('[role="dialog"]').filter({ has: page.getByRole("heading", { name: "More filters" }) });

  if (configuredDomain) {
    await filtersPanel.getByLabel(configuredDomain, { exact: true }).check();
  } else {
    const firstDomainCheckbox = filtersPanel.locator(".checkbox-grid input[type='checkbox']").first();
    await expect(firstDomainCheckbox).toBeVisible();
    await firstDomainCheckbox.check();
  }

  await filtersPanel.getByLabel("Include SPF").selectOption("pass");
  await page.getByRole("button", { name: "Apply filters" }).click();
}

test.describe("frontend-next search coverage", () => {
  test("aggregate search restores filter state from query params", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/search");

    await expect(page.getByRole("heading", { name: "Search", exact: true })).toBeVisible();
    await applyDefaultAggregateFilters(page);

    await expect(page).toHaveURL(/\/search\?/);
    await expect(page.getByLabel("Free-text search")).toHaveValue(process.env.DMARC_E2E_SEARCH_QUERY ?? "google");
    await expect(page.getByText(`Search: ${process.env.DMARC_E2E_SEARCH_QUERY ?? "google"}`)).toBeVisible();
    await expect(page.getByText("SPF: Pass")).toBeVisible();

    await page.reload();

    await expect(page.getByRole("heading", { name: "Search", exact: true })).toBeVisible();
    await expect(page.getByLabel("Free-text search")).toHaveValue(process.env.DMARC_E2E_SEARCH_QUERY ?? "google");
    await expect(page.getByText("SPF: Pass")).toBeVisible();

    await page.getByRole("button", { name: "More filters" }).click();
    await expect(page.locator('[role="dialog"]').filter({ has: page.getByRole("heading", { name: "More filters" }) }).getByLabel("Include SPF")).toHaveValue("pass");

    if (process.env.DMARC_E2E_SEARCH_DOMAIN) {
      await expect(
        page.locator('[role="dialog"]').filter({ has: page.getByRole("heading", { name: "More filters" }) }).getByLabel(
          process.env.DMARC_E2E_SEARCH_DOMAIN,
          { exact: true },
        ),
      ).toBeChecked();
    } else {
      await expect(
        page.locator('[role="dialog"]').filter({ has: page.getByRole("heading", { name: "More filters" }) }).locator(
          ".checkbox-grid input[type='checkbox']",
        ).first(),
      ).toBeChecked();
    }
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
    await expect(page.getByText("Forensic reports use domain and date filters only.")).toBeVisible();

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

    const firstQuickFilter = page.locator(".cell-action-trigger").first();
    test.skip((await firstQuickFilter.count()) === 0, "Quick-filter coverage needs seeded aggregate search results.");

    const chipCountBefore = await page.locator(".filter-chip").count();
    const urlBefore = page.url();
    await firstQuickFilter.click();
    await page.locator(".cell-action-item").first().click();

    await expect(page).toHaveURL(/search\?/);
    expect(page.url()).not.toBe(urlBefore);
    const chipCountAfter = await page.locator(".filter-chip").count();
    expect(chipCountAfter).toBeGreaterThanOrEqual(chipCountBefore);
  });
});
