import { expect, type Page } from "@playwright/test";

type SeededRole = "super-admin" | "admin" | "manager" | "viewer";

const roleCredentialEnv: Record<SeededRole, { username: string; password: string }> = {
  "super-admin": {
    username: "DMARC_E2E_SUPERADMIN_USERNAME",
    password: "DMARC_E2E_SUPERADMIN_PASSWORD",
  },
  admin: {
    username: "DMARC_E2E_ADMIN_USERNAME",
    password: "DMARC_E2E_ADMIN_PASSWORD",
  },
  manager: {
    username: "DMARC_E2E_MANAGER_USERNAME",
    password: "DMARC_E2E_MANAGER_PASSWORD",
  },
  viewer: {
    username: "DMARC_E2E_VIEWER_USERNAME",
    password: "DMARC_E2E_VIEWER_PASSWORD",
  },
};

function getEnv(name: string): string | undefined {
  const value = process.env[name];
  return value && value.length > 0 ? value : undefined;
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required E2E env var: ${name}`);
  }
  return value;
}

export function hasSeededCredentials(role: SeededRole): boolean {
  const env = roleCredentialEnv[role];
  return Boolean(getEnv(env.username) && getEnv(env.password));
}

export function getSeededCredentials(role: SeededRole) {
  const env = roleCredentialEnv[role];
  return {
    username: requireEnv(env.username),
    password: requireEnv(env.password),
  };
}

export async function loginAsRole(page: Page, role: SeededRole) {
  const credentials = getSeededCredentials(role);

  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();

  await page.getByLabel("Username").fill(credentials.username);
  await page.getByLabel("Password").fill(credentials.password);
  await page.getByRole("button", { name: "Sign in" }).click();

  await page.waitForURL("**/domains");
  await expect(page.getByRole("heading", { name: "Domains" })).toBeVisible();
}

export async function loginAsSuperAdmin(page: Page) {
  await loginAsRole(page, "super-admin");
}
