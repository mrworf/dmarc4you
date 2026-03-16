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

  if (configuredDomain) {
    await page.getByLabel(configuredDomain).check();
  } else {
    const firstDomainCheckbox = page.locator(".checkbox-grid input[type='checkbox']").first();
    await expect(firstDomainCheckbox).toBeVisible();
    await firstDomainCheckbox.check();
  }

  await page.getByLabel("Free-text query").fill(process.env.DMARC_E2E_SEARCH_QUERY ?? "google");
  await page.getByLabel("Include SPF").selectOption("pass");
}

test.describe("frontend-next search coverage", () => {
  test("aggregate search restores filter state from query params", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/search");

    await expect(page.getByRole("heading", { name: "Search" })).toBeVisible();
    await applyDefaultAggregateFilters(page);
    await page.getByRole("button", { name: "Search" }).click();

    await expect(page).toHaveURL(/\/search\?/);
    await expect(page.getByLabel("Free-text query")).toHaveValue(process.env.DMARC_E2E_SEARCH_QUERY ?? "google");
    await expect(page.getByLabel("Include SPF")).toHaveValue("pass");

    await page.reload();

    await expect(page.getByRole("heading", { name: "Search" })).toBeVisible();
    await expect(page.getByLabel("Free-text query")).toHaveValue(process.env.DMARC_E2E_SEARCH_QUERY ?? "google");
    await expect(page.getByLabel("Include SPF")).toHaveValue("pass");

    if (process.env.DMARC_E2E_SEARCH_DOMAIN) {
      await expect(page.getByLabel(process.env.DMARC_E2E_SEARCH_DOMAIN)).toBeChecked();
    } else {
      await expect(page.locator(".checkbox-grid input[type='checkbox']").first()).toBeChecked();
    }
  });

  test("search route switches between aggregate and forensic modes", async ({ page }) => {
    await loginAsSuperAdmin(page);
    await page.goto("/search");

    await expect(page.getByRole("heading", { name: "Aggregate results" })).toBeVisible();
    await page.getByLabel("Report type").selectOption("forensic");
    await page.getByRole("button", { name: "Search" }).click();

    await expect(page).toHaveURL(/report_type=forensic/);
    await expect(page.getByRole("heading", { name: "Forensic reports" })).toBeVisible();
    await expect(page.getByLabel("Free-text query")).toBeDisabled();
    await expect(page.getByText("aggregate-only query and include/exclude filters stay disabled")).toBeVisible();

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

    await expect(page.getByRole("heading", { name: "Search" })).toBeVisible();
    const paginationSummary = page.locator(".pagination-row .status-text");
    await expect(paginationSummary).toBeVisible();

    const summaryText = (await paginationSummary.textContent()) ?? "";
    const match = summaryText.match(/Page\s+(\d+)\s+of\s+(\d+)/);
    const totalPages = match ? Number.parseInt(match[2], 10) : 1;

    test.skip(
      totalPages < 2,
      "Pagination coverage needs seeded search data that returns more than one page for the selected filters.",
    );

    await page.getByRole("button", { name: "Next" }).click();
    await expect(page).toHaveURL(/page=2/);
    await expect(paginationSummary).toContainText("Page 2 of");

    await page.reload();

    await expect(page).toHaveURL(/page=2/);
    await expect(paginationSummary).toContainText("Page 2 of");
  });
});
