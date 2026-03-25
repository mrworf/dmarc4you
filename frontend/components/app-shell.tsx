"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";

import { apiClient, ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/context";
import type {
  AuthMeResponse,
  DomainsResponse,
  UpdatePasswordBody,
  UpdatePasswordResponse,
  UpdateProfileBody,
  UserRole,
} from "@/lib/api/types";

type AppShellProps = {
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  actions?: ReactNode;
};

type NavItem = {
  href: string;
  label: string;
  roles?: UserRole[];
};

const navItems: NavItem[] = [
  { href: "/domains", label: "Domains" },
  { href: "/dashboards", label: "Dashboards" },
  { href: "/search", label: "Search" },
  { href: "/upload", label: "Upload" },
  { href: "/ingest-jobs", label: "Ingest Jobs" },
  { href: "/users", label: "Users", roles: ["super-admin", "admin"] },
  { href: "/apikeys", label: "API Keys", roles: ["super-admin", "admin"] },
  { href: "/audit", label: "Audit", roles: ["super-admin"] },
];

export function AppShell({ title, description, children, actions }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { allDomains, clearAuth, domainIds, logout, refresh, user } = useAuth();
  const [isNavOpen, setIsNavOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  useEffect(() => {
    if (!isProfileOpen) {
      return;
    }

    setFullName(user?.full_name ?? "");
    setEmail(user?.email ?? "");
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsProfileOpen(false);
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isProfileOpen, user]);

  const profileDomainsQuery = useQuery({
    queryKey: ["profile-domains"],
    queryFn: () => apiClient.get<DomainsResponse>("/api/v1/domains"),
    enabled: isProfileOpen && !!user && !allDomains,
  });

  const updateProfile = useMutation({
    mutationFn: (body: UpdateProfileBody) => apiClient.put<AuthMeResponse>("/api/v1/auth/me", body),
    onSuccess: async () => {
      await refresh();
      setIsProfileOpen(false);
    },
  });

  const updatePassword = useMutation({
    mutationFn: (body: UpdatePasswordBody) => apiClient.put<UpdatePasswordResponse>("/api/v1/auth/password", body),
    onSuccess: () => {
      clearAuth();
      setIsProfileOpen(false);
      router.replace("/login?passwordChanged=1");
    },
  });

  const visibleDomainNames = useMemo(() => {
    if (allDomains) {
      return [];
    }
    const visibleDomains = profileDomainsQuery.data?.domains ?? [];
    if (visibleDomains.length) {
      return visibleDomains.map((domain) => domain.name);
    }
    return domainIds;
  }, [allDomains, domainIds, profileDomainsQuery.data?.domains]);

  async function handleProfileSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await updateProfile.mutateAsync({
      full_name: fullName.trim() || null,
      email: email.trim() || null,
    });
  }

  async function handlePasswordSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPassword.length < 12) {
      return;
    }
    if (newPassword !== confirmPassword) {
      return;
    }
    await updatePassword.mutateAsync({
      current_password: currentPassword,
      new_password: newPassword,
    });
  }

  const visibleItems = navItems.filter((item) => !item.roles || (user && item.roles.includes(user.role)));
  const profileName = user?.full_name?.trim() || user?.username || "Account";
  const profileError = updateProfile.error instanceof ApiError ? updateProfile.error.message : null;
  const passwordError =
    newPassword && confirmPassword && newPassword !== confirmPassword
      ? "Passwords do not match"
      : updatePassword.error instanceof ApiError
        ? updatePassword.error.message
        : newPassword && newPassword.length > 0 && newPassword.length < 12
          ? "Password must be at least 12 characters"
          : null;

  return (
    <main className="app-frame app-frame-app app-shell-layout">
      <div className="mobile-nav-row">
        <button
          aria-expanded={isNavOpen}
          className="button-secondary nav-toggle"
          onClick={() => setIsNavOpen(true)}
          type="button"
        >
          Menu
        </button>
      </div>
      {isNavOpen ? <div className="nav-scrim" onClick={() => setIsNavOpen(false)} role="presentation" /> : null}
      <aside className="surface-card sidebar" data-open={isNavOpen}>
        <div className="stack">
          <div className="sidebar-brand">
            <p className="eyebrow">DMARCWatch</p>
          </div>
          {user ? (
            <button className="profile-trigger" onClick={() => setIsProfileOpen(true)} type="button">
              <span className="profile-name">{profileName}</span>
              <span className="profile-meta">
                @{user.username} · {user.role}
              </span>
              <span className="profile-meta">{user.email ?? "Local account"}</span>
            </button>
          ) : null}
        </div>
        <nav className="nav-links">
          {visibleItems.map((item) => (
            <Link
              className="nav-link"
              data-active={pathname === item.href || pathname.startsWith(`${item.href}/`)}
              href={item.href}
              key={item.href}
              onClick={() => setIsNavOpen(false)}
            >
              <span>{item.label}</span>
              <span aria-hidden="true">›</span>
            </Link>
          ))}
        </nav>
        <button className="button-secondary" onClick={handleLogout} type="button">
          Log out
        </button>
      </aside>
      <section className="content-grid">
        <header className="hero-card page-hero">
          <div className={`page-header-copy${description ? "" : " page-header-copy-single"}`}>
            <h2 className="page-title page-title-compact">{title}</h2>
            {description ? <p className="lede page-header-description">{description}</p> : null}
          </div>
          {actions}
        </header>
        {children}
      </section>
      {isProfileOpen && user ? (
        <div className="modal-backdrop" onClick={() => setIsProfileOpen(false)} role="presentation">
          <div
            aria-modal="true"
            className="modal-card surface-card profile-dialog"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
          >
            <div className="modal-header">
              <div className="stack" style={{ gap: 8 }}>
                <p className="eyebrow">Profile</p>
                <h2 style={{ margin: 0 }}>My profile</h2>
                <p className="status-text" style={{ margin: 0 }}>
                  Update your full name and email. Username, role, and domain access stay read-only here.
                </p>
              </div>
              <button aria-label="Close profile" className="icon-button" onClick={() => setIsProfileOpen(false)} type="button">
                ×
              </button>
            </div>
            <div className="stack">
              <form className="stack" onSubmit={handleProfileSave}>
                <div className="detail-grid">
                  <label className="field-label detail-card detail-card-wide">
                    Full name
                    <input className="field-input" onChange={(event) => setFullName(event.target.value)} value={fullName} />
                  </label>
                  <label className="field-label detail-card detail-card-wide">
                    Email
                    <input className="field-input" onChange={(event) => setEmail(event.target.value)} type="email" value={email} />
                  </label>
                  <article className="detail-card">
                    <p className="stat-label">Role</p>
                    <strong>{user.role}</strong>
                  </article>
                  <article className="detail-card">
                    <p className="stat-label">Username</p>
                    <strong>@{user.username}</strong>
                  </article>
                  {!allDomains ? (
                    <article className="detail-card detail-card-wide">
                      <p className="stat-label">Domains</p>
                      {profileDomainsQuery.isLoading ? <span className="status-text">Loading domains...</span> : null}
                      {profileDomainsQuery.error ? (
                        <span className="error-text">
                          {profileDomainsQuery.error instanceof Error ? profileDomainsQuery.error.message : "Failed to load domains"}
                        </span>
                      ) : null}
                      {!profileDomainsQuery.isLoading && !profileDomainsQuery.error ? (
                        visibleDomainNames.length ? (
                          <div className="pill-row profile-domain-list">
                            {visibleDomainNames.map((domainName) => (
                              <span className="pill" key={domainName}>
                                {domainName}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="status-text">No domains assigned.</span>
                        )
                      ) : null}
                    </article>
                  ) : null}
                </div>
                {profileError ? <p className="error-text">{profileError}</p> : null}
                <div className="dialog-actions">
                  <button className="button-secondary" onClick={() => setIsProfileOpen(false)} type="button">
                    Cancel
                  </button>
                  <button className="button-primary" disabled={updateProfile.isPending} type="submit">
                    {updateProfile.isPending ? "Saving..." : "Save profile"}
                  </button>
                </div>
              </form>
              <form className="stack" onSubmit={handlePasswordSave}>
                <div className="modal-header" style={{ padding: 0, border: 0 }}>
                  <div className="stack" style={{ gap: 8 }}>
                    <p className="eyebrow">Password</p>
                    <h3 style={{ margin: 0 }}>Change password</h3>
                    <p className="status-text" style={{ margin: 0 }}>
                      Saving a new password signs this account out everywhere and requires a fresh login.
                    </p>
                  </div>
                </div>
                <div className="detail-grid">
                  <label className="field-label detail-card detail-card-wide">
                    Current password
                    <input
                      className="field-input"
                      onChange={(event) => setCurrentPassword(event.target.value)}
                      type="password"
                      value={currentPassword}
                    />
                  </label>
                  <label className="field-label detail-card detail-card-wide">
                    New password
                    <input
                      className="field-input"
                      onChange={(event) => setNewPassword(event.target.value)}
                      type="password"
                      value={newPassword}
                    />
                  </label>
                  <label className="field-label detail-card detail-card-wide">
                    Confirm new password
                    <input
                      className="field-input"
                      onChange={(event) => setConfirmPassword(event.target.value)}
                      type="password"
                      value={confirmPassword}
                    />
                  </label>
                </div>
                {passwordError ? <p className="error-text">{passwordError}</p> : null}
                <div className="dialog-actions">
                  <button
                    className="button-primary"
                    disabled={
                      updatePassword.isPending ||
                      !currentPassword ||
                      !newPassword ||
                      !confirmPassword ||
                      Boolean(passwordError)
                    }
                    type="submit"
                  >
                    {updatePassword.isPending ? "Updating..." : "Change password"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
