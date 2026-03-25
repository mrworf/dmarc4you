import { expect, type Page } from "@playwright/test";

type SeededRole = "super-admin" | "admin" | "manager" | "viewer";

const roleCredentialEnv: Record<
  SeededRole,
  { username: string; password: string; defaultUsername: string; defaultPassword: string }
> = {
  "super-admin": {
    username: "DMARC_E2E_SUPERADMIN_USERNAME",
    password: "DMARC_E2E_SUPERADMIN_PASSWORD",
    defaultUsername: "admin",
    defaultPassword: "seed-super-admin-pass",
  },
  admin: {
    username: "DMARC_E2E_ADMIN_USERNAME",
    password: "DMARC_E2E_ADMIN_PASSWORD",
    defaultUsername: "e2e-admin",
    defaultPassword: "seed-admin-pass",
  },
  manager: {
    username: "DMARC_E2E_MANAGER_USERNAME",
    password: "DMARC_E2E_MANAGER_PASSWORD",
    defaultUsername: "e2e-manager",
    defaultPassword: "seed-manager-pass",
  },
  viewer: {
    username: "DMARC_E2E_VIEWER_USERNAME",
    password: "DMARC_E2E_VIEWER_PASSWORD",
    defaultUsername: "e2e-viewer",
    defaultPassword: "seed-viewer-pass",
  },
};

function getEnv(name: string): string | undefined {
  const value = process.env[name];
  return value && value.length > 0 ? value : undefined;
}

export function hasSeededCredentials(role: SeededRole): boolean {
  const credentials = roleCredentialEnv[role];
  return Boolean(
    (getEnv(credentials.username) ?? credentials.defaultUsername) &&
      (getEnv(credentials.password) ?? credentials.defaultPassword),
  );
}

export function getSeededCredentials(role: SeededRole) {
  const env = roleCredentialEnv[role];
  return {
    username: getEnv(env.username) ?? env.defaultUsername,
    password: getEnv(env.password) ?? env.defaultPassword,
  };
}

export async function loginAsRole(page: Page, role: SeededRole) {
  const credentials = getSeededCredentials(role);

  for (let attempt = 0; attempt < 3; attempt += 1) {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();

    await page.getByLabel("Username").fill(credentials.username);
    await page.getByLabel("Password").fill(credentials.password);
    await page.getByRole("button", { name: "Sign in" }).click();

    try {
      await page.waitForURL("**/domains", { timeout: 10_000 });
      await expect(page.getByRole("heading", { name: "Domains" })).toBeVisible();
      return;
    } catch (error) {
      const fetchFailure = page.getByText("Failed to fetch", { exact: true });
      if (attempt === 2) {
        throw error;
      }

      if (await fetchFailure.count()) {
        await page.waitForTimeout(500);
        continue;
      }
    }
  }
}

export async function loginAsSuperAdmin(page: Page) {
  await loginAsRole(page, "super-admin");
}
