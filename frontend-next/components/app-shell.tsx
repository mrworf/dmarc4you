"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/lib/auth/context";
import type { UserRole } from "@/lib/api/types";

type AppShellProps = {
  title: string;
  description: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
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
  const { logout, user } = useAuth();
  const [isNavOpen, setIsNavOpen] = useState(false);

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  const visibleItems = navItems.filter((item) => !item.roles || (user && item.roles.includes(user.role)));

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
          <p className="eyebrow">DMARC Analyzer</p>
          <h1 style={{ margin: 0, fontSize: "1.8rem" }}>Operations console</h1>
          {user ? (
            <>
              <span className="pill">{user.role}</span>
              <div className="status-text">
              <strong style={{ color: "var(--ink)" }}>{user.username}</strong>
                <br />
                {user.email ?? "Local account"}
              </div>
            </>
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
        <header className="hero-card stack">
          <div className="stack" style={{ gap: 8 }}>
            <p className="eyebrow">Workspace</p>
            <h2 className="page-title" style={{ fontSize: "clamp(2rem, 3vw, 3rem)" }}>
              {title}
            </h2>
            <p className="lede">{description}</p>
          </div>
          {actions}
        </header>
        {children}
      </section>
    </main>
  );
}
