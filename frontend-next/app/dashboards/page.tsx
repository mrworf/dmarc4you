"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { AppShell } from "@/components/app-shell";
import { AuthGuard } from "@/components/auth-guard";
import { CreateDashboardForm, type CreateDashboardValues } from "@/components/create-dashboard-form";
import { DashboardList } from "@/components/dashboard-list";
import { ImportDashboardForm } from "@/components/import-dashboard-form";
import { SlideOverPanel } from "@/components/slide-over-panel";
import { apiClient, ApiError } from "@/lib/api/client";
import type { CreateDashboardBody, DashboardsResponse, DomainsResponse } from "@/lib/api/types";

function DashboardsContent() {
  const queryClient = useQueryClient();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const dashboardsQuery = useQuery({
    queryKey: ["dashboards"],
    queryFn: () => apiClient.get<DashboardsResponse>("/api/v1/dashboards"),
  });
  const domainsQuery = useQuery({
    queryKey: ["domains"],
    queryFn: () => apiClient.get<DomainsResponse>("/api/v1/domains"),
  });

  const createDashboard = useMutation({
    mutationFn: (values: CreateDashboardBody) => apiClient.post("/api/v1/dashboards", values),
    onSuccess: async () => {
      setIsCreateOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["dashboards"] });
    },
  });

  async function handleCreateDashboard(values: CreateDashboardValues) {
    await createDashboard.mutateAsync(values);
  }

  const domains = domainsQuery.data?.domains ?? [];
  const dashboards = dashboardsQuery.data?.dashboards ?? [];
  const mutationError =
    createDashboard.error instanceof ApiError ? createDashboard.error.message : "Failed to create dashboard";

  return (
    <AppShell
      title="Dashboards"
      description="Monitor saved dashboards, create new views, and import shared configurations."
      actions={
        <div className="section-actions">
          <button className="button-primary" onClick={() => setIsCreateOpen(true)} type="button">
            Create dashboard
          </button>
          <button className="button-secondary" onClick={() => setIsImportOpen(true)} type="button">
            Import dashboard
          </button>
          <button className="button-secondary" onClick={() => dashboardsQuery.refetch()} type="button">
            Refresh
          </button>
        </div>
      }
    >
      <section className="panel-grid">
        <article className="stat-card">
          <p className="stat-label">Owned dashboards</p>
          <p className="stat-value">{dashboards.length}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Available domains</p>
          <p className="stat-value">{domains.length}</p>
        </article>
      </section>

      <section className="surface-card stack">
        <div className="section-heading">
          <div className="stack" style={{ gap: 8 }}>
            <h2 className="section-title">Your dashboards</h2>
            <p className="section-intro">Open an existing dashboard or start a new one from the actions above.</p>
          </div>
        </div>
        {dashboardsQuery.isLoading ? <p className="status-text">Loading dashboards...</p> : null}
        {dashboardsQuery.error ? (
          <p className="error-text">
            {dashboardsQuery.error instanceof Error ? dashboardsQuery.error.message : "Failed to load dashboards"}
          </p>
        ) : null}
        {dashboardsQuery.data ? <DashboardList dashboards={dashboards} /> : null}
      </section>

      <SlideOverPanel
        description="Choose a name, add the domains you want to track, and create a new shared dashboard."
        footer={undefined}
        onClose={() => setIsCreateOpen(false)}
        open={isCreateOpen}
        title="Create dashboard"
      >
        {domainsQuery.isLoading ? <p className="status-text">Loading domains...</p> : null}
        {domainsQuery.error ? (
          <p className="error-text">{domainsQuery.error instanceof Error ? domainsQuery.error.message : "Failed to load domains"}</p>
        ) : null}
        {createDashboard.isError ? <p className="error-text">{mutationError}</p> : null}
        <CreateDashboardForm
          domains={domains}
          isSubmitting={createDashboard.isPending}
          onSubmit={handleCreateDashboard}
        />
      </SlideOverPanel>

      <SlideOverPanel
        description="Paste exported YAML, remap the source domains, and create a new dashboard for this workspace."
        onClose={() => setIsImportOpen(false)}
        open={isImportOpen}
        title="Import dashboard"
      >
        {domainsQuery.isLoading ? <p className="status-text">Loading domains...</p> : null}
        {domainsQuery.error ? (
          <p className="error-text">{domainsQuery.error instanceof Error ? domainsQuery.error.message : "Failed to load domains"}</p>
        ) : null}
        <ImportDashboardForm compact domains={domains} />
      </SlideOverPanel>
    </AppShell>
  );
}

export default function DashboardsPage() {
  return (
    <AuthGuard>
      <DashboardsContent />
    </AuthGuard>
  );
}
