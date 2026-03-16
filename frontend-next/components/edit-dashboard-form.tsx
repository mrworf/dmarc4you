"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import type { DashboardDetailResponse, DomainSummary } from "@/lib/api/types";
import { dashboardColumnOptions, defaultVisibleColumns } from "@/lib/dashboard-columns";

const editDashboardSchema = z.object({
  name: z.string().trim().min(1, "Name is required"),
  description: z.string().optional(),
  domain_ids: z.array(z.string()).min(1, "Select at least one domain"),
  visible_columns: z.array(z.string()).min(1, "Select at least one visible field"),
});

export type EditDashboardValues = z.infer<typeof editDashboardSchema>;

export function EditDashboardForm({
  dashboard,
  domains,
  isSubmitting,
  onCancel,
  onSubmit,
}: {
  dashboard: DashboardDetailResponse;
  domains: DomainSummary[];
  isSubmitting: boolean;
  onCancel: () => void;
  onSubmit: (values: EditDashboardValues) => Promise<void>;
}) {
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<EditDashboardValues>({
    resolver: zodResolver(editDashboardSchema),
    defaultValues: {
      name: dashboard.name,
      description: dashboard.description ?? "",
      domain_ids: dashboard.domain_ids,
      visible_columns: dashboard.visible_columns?.length ? dashboard.visible_columns : defaultVisibleColumns,
    },
  });

  useEffect(() => {
    reset({
      name: dashboard.name,
      description: dashboard.description ?? "",
      domain_ids: dashboard.domain_ids,
      visible_columns: dashboard.visible_columns?.length ? dashboard.visible_columns : defaultVisibleColumns,
    });
  }, [dashboard, reset]);

  return (
    <form className="stack" onSubmit={handleSubmit(onSubmit)}>
      <label className="field-label">
        Name
        <input className="field-input" {...register("name")} />
        {errors.name ? <span className="error-text">{errors.name.message}</span> : null}
      </label>
      <label className="field-label">
        Description
        <textarea className="field-input" {...register("description")} rows={3} />
      </label>
      <div className="stack" style={{ gap: 10 }}>
        <span className="field-label" style={{ gap: 0 }}>
          Domains
        </span>
        {domains.length ? (
          domains.map((domain) => (
            <label className="checkbox-card" key={domain.id}>
              <input type="checkbox" value={domain.id} {...register("domain_ids")} />
              <span>{domain.name}</span>
            </label>
          ))
        ) : (
          <p className="status-text">No active domains are available yet.</p>
        )}
        {errors.domain_ids ? <span className="error-text">{errors.domain_ids.message}</span> : null}
      </div>
      <div className="stack" style={{ gap: 10 }}>
        <div className="section-actions">
          <span className="field-label" style={{ gap: 0 }}>
            Visible fields
          </span>
          <button
            className="button-link"
            onClick={() => reset({
              name: dashboard.name,
              description: dashboard.description ?? "",
              domain_ids: dashboard.domain_ids,
              visible_columns: defaultVisibleColumns,
            })}
            type="button"
          >
            Reset to default
          </button>
        </div>
        {dashboardColumnOptions.map((column) => (
          <label className="checkbox-card" key={column.value}>
            <input type="checkbox" value={column.value} {...register("visible_columns")} />
            <span>{column.label}</span>
          </label>
        ))}
        {errors.visible_columns ? <span className="error-text">{errors.visible_columns.message}</span> : null}
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <button className="button-primary" disabled={isSubmitting || !domains.length} type="submit">
          {isSubmitting ? "Saving..." : "Save changes"}
        </button>
        <button className="button-secondary" onClick={onCancel} type="button">
          Cancel
        </button>
      </div>
    </form>
  );
}
