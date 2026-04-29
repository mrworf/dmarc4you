import { expect, test } from "@playwright/test";

import { loginAsSuperAdmin } from "./auth";

test("containerized frontend can sign in against the configured backend endpoint", async ({ page }) => {
  await loginAsSuperAdmin(page);

  await expect(page.getByRole("heading", { name: "Domains", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Domain inventory" })).toBeVisible();
});
