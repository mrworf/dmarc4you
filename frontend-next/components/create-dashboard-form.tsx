"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import type { DomainSummary } from "@/lib/api/types";
import { dashboardColumnOptions, defaultVisibleColumns } from "@/lib/dashboard-columns";

const createDashboardSchema = z.object({
  name: z.string().trim().min(1, "Name is required"),
  description: z.string().optional(),
  domain_ids: z.array(z.string()).min(1, "Select at least one domain"),
  visible_columns: z.array(z.string()).min(1, "Select at least one visible field"),
});

export type CreateDashboardValues = z.infer<typeof createDashboardSchema>;

export function CreateDashboardForm({
  domains,
  isSubmitting,
  onSubmit,
}: {
  domains: DomainSummary[];
  isSubmitting: boolean;
  onSubmit: (values: CreateDashboardValues) => Promise<void>;
}) {
  const {
    formState: { errors },
    handleSubmit,
    register,
  } = useForm<CreateDashboardValues>({
    resolver: zodResolver(createDashboardSchema),
    defaultValues: {
      name: "",
      description: "",
      domain_ids: [],
      visible_columns: defaultVisibleColumns,
    },
  });

  return (
    <form className="stack" onSubmit={handleSubmit(onSubmit)}>
      <label className="field-label">
        Name
        <input className="field-input" {...register("name")} placeholder="Deliverability Overview" />
        {errors.name ? <span className="error-text">{errors.name.message}</span> : null}
      </label>
      <label className="field-label">
        Description
        <textarea className="field-input" {...register("description")} placeholder="Optional summary for your team" rows={3} />
      </label>
      <div className="stack" style={{ gap: 10 }}>
        <span className="field-label" style={{ gap: 0 }}>
          Domains
        </span>
        {domains.length ? (
          domains.map((domain) => (
            <label
              key={domain.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "12px 14px",
                border: "1px solid var(--line)",
                borderRadius: 14,
                background: "rgba(255,255,255,0.75)",
              }}
            >
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
        <span className="field-label" style={{ gap: 0 }}>
          Visible fields
        </span>
        {dashboardColumnOptions.map((column) => (
          <label className="checkbox-card" key={column.value}>
            <input type="checkbox" value={column.value} {...register("visible_columns")} />
            <span>{column.label}</span>
          </label>
        ))}
        {errors.visible_columns ? <span className="error-text">{errors.visible_columns.message}</span> : null}
      </div>
      <button className="button-primary" disabled={isSubmitting || !domains.length} type="submit">
        {isSubmitting ? "Creating..." : "Create dashboard"}
      </button>
    </form>
  );
}
