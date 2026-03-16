"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import type { DashboardDetailResponse, DomainSummary } from "@/lib/api/types";

const editDashboardSchema = z.object({
  name: z.string().trim().min(1, "Name is required"),
  description: z.string().optional(),
  domain_ids: z.array(z.string()).min(1, "Select at least one domain"),
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
    },
  });

  useEffect(() => {
    reset({
      name: dashboard.name,
      description: dashboard.description ?? "",
      domain_ids: dashboard.domain_ids,
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
