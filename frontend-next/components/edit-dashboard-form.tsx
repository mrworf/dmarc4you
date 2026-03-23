"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import type { DashboardDetailResponse, DomainSummary } from "@/lib/api/types";
import { dashboardChartYAxisOptions, defaultDashboardChartYAxis } from "@/lib/dashboard-chart-options";
import { dashboardColumnOptions, defaultVisibleColumns } from "@/lib/dashboard-columns";

const editDashboardSchema = z.object({
  name: z.string().trim().min(1, "Name is required"),
  description: z.string().optional(),
  domain_ids: z.array(z.string()).min(1, "Select at least one domain"),
  visible_columns: z.array(z.string()).min(1, "Select at least one visible field"),
  chart_y_axis: z.enum(["message_count", "row_count", "report_count"]),
});

export type EditDashboardValues = z.infer<typeof editDashboardSchema>;

type DashboardColumnOption = (typeof dashboardColumnOptions)[number];

function moveItem(values: string[], fromIndex: number, toIndex: number): string[] {
  if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0 || fromIndex >= values.length || toIndex >= values.length) {
    return values;
  }
  const nextValues = [...values];
  const [moved] = nextValues.splice(fromIndex, 1);
  nextValues.splice(toIndex, 0, moved);
  return nextValues;
}

function findColumnOption(value: string): DashboardColumnOption | undefined {
  return dashboardColumnOptions.find((option) => option.value === value);
}

function toggleValue(values: string[], value: string): string[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

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
  const initialVisibleColumns = dashboard.visible_columns?.length ? dashboard.visible_columns : defaultVisibleColumns;
  const [draggedColumn, setDraggedColumn] = useState<string | null>(null);
  const [hoveredColumn, setHoveredColumn] = useState<string | null>(null);
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
    setValue,
    watch,
  } = useForm<EditDashboardValues>({
    resolver: zodResolver(editDashboardSchema),
    defaultValues: {
      name: dashboard.name,
      description: dashboard.description ?? "",
      domain_ids: dashboard.domain_ids,
      visible_columns: initialVisibleColumns,
      chart_y_axis: dashboard.chart_y_axis ?? defaultDashboardChartYAxis,
    },
  });

  const selectedDomainIds = watch("domain_ids");
  const selectedColumns = watch("visible_columns");
  const availableColumns = dashboardColumnOptions.filter((option) => !selectedColumns.includes(option.value));

  useEffect(() => {
    reset({
      name: dashboard.name,
      description: dashboard.description ?? "",
      domain_ids: dashboard.domain_ids,
      visible_columns: dashboard.visible_columns?.length ? dashboard.visible_columns : defaultVisibleColumns,
      chart_y_axis: dashboard.chart_y_axis ?? defaultDashboardChartYAxis,
    });
    setDraggedColumn(null);
    setHoveredColumn(null);
  }, [dashboard, reset]);

  function updateVisibleColumns(nextValues: string[]) {
    setValue("visible_columns", nextValues, { shouldDirty: true, shouldValidate: true });
  }

  function resetVisibleColumns() {
    updateVisibleColumns(defaultVisibleColumns);
  }

  function moveColumn(column: string, direction: -1 | 1) {
    const index = selectedColumns.indexOf(column);
    updateVisibleColumns(moveItem(selectedColumns, index, index + direction));
  }

  function removeColumn(column: string) {
    updateVisibleColumns(selectedColumns.filter((value) => value !== column));
  }

  function addColumn(column: string) {
    updateVisibleColumns([...selectedColumns, column]);
  }

  function clearDragState() {
    setDraggedColumn(null);
    setHoveredColumn(null);
  }

  function moveDraggedColumn(targetColumn: string) {
    if (!draggedColumn || draggedColumn === targetColumn) {
      return;
    }
    const fromIndex = selectedColumns.indexOf(draggedColumn);
    const toIndex = selectedColumns.indexOf(targetColumn);
    if (fromIndex === -1 || toIndex === -1 || fromIndex === toIndex) {
      return;
    }
    updateVisibleColumns(moveItem(selectedColumns, fromIndex, toIndex));
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    clearDragState();
  }

  function handleDragStart(column: string, event: React.DragEvent<HTMLButtonElement>) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", column);
    setDraggedColumn(column);
    setHoveredColumn(column);
  }

  function handleDragOver(targetColumn: string, event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    if (!draggedColumn) {
      return;
    }
    event.dataTransfer.dropEffect = "move";
    setHoveredColumn(targetColumn);
    moveDraggedColumn(targetColumn);
  }

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
              <input
                checked={selectedDomainIds.includes(domain.id)}
                onChange={() =>
                  setValue("domain_ids", toggleValue(selectedDomainIds, domain.id), {
                    shouldDirty: true,
                    shouldValidate: true,
                  })
                }
                type="checkbox"
              />
              <span>{domain.name}</span>
            </label>
          ))
        ) : (
          <p className="status-text">No active domains are available yet.</p>
        )}
        {errors.domain_ids ? <span className="error-text">{errors.domain_ids.message}</span> : null}
      </div>
      <div className="stack" style={{ gap: 14 }}>
        <div className="section-actions">
          <span className="field-label" style={{ gap: 0 }}>
            Visible fields
          </span>
          <button className="button-link" onClick={resetVisibleColumns} type="button">
            Reset to default
          </button>
        </div>
        <p className="status-text">
          Reorder saved fields with drag handles or move buttons. Remove anything you do not want shown by default.
        </p>
        <div className="selection-list">
          {selectedColumns.map((column, index) => {
            const option = findColumnOption(column);
            if (!option) {
              return null;
            }
            return (
              <div
                className="selection-row"
                data-dragging={draggedColumn === column}
                data-drop-target={hoveredColumn === column && draggedColumn !== column}
                data-column-value={column}
                key={column}
                onDragEnter={() => setHoveredColumn(column)}
                onDragOver={(event) => handleDragOver(column, event)}
                onDragLeave={() => setHoveredColumn((current) => (current === column ? null : current))}
                onDrop={(event) => handleDrop(event)}
              >
                <button
                  aria-label={`Drag to reorder ${option.label}`}
                  aria-grabbed={draggedColumn === column}
                  className="drag-handle"
                  draggable
                  onDragEnd={clearDragState}
                  onDragStart={(event) => handleDragStart(column, event)}
                  type="button"
                >
                  ::
                </button>
                <div className="selection-row-copy">
                  <span className="selection-row-title">{option.label}</span>
                  <span className="selection-row-description">Shown in position {index + 1}</span>
                </div>
                <div className="selection-row-actions">
                  <button className="button-secondary" disabled={index === 0} onClick={() => moveColumn(column, -1)} type="button">
                    Move up
                  </button>
                  <button
                    className="button-secondary"
                    disabled={index === selectedColumns.length - 1}
                    onClick={() => moveColumn(column, 1)}
                    type="button"
                  >
                    Move down
                  </button>
                  <button className="button-secondary" onClick={() => removeColumn(column)} type="button">
                    Remove
                  </button>
                </div>
              </div>
            );
          })}
        </div>
        {errors.visible_columns ? <span className="error-text">{errors.visible_columns.message}</span> : null}
      </div>
      <div className="stack" style={{ gap: 12 }}>
        <span className="field-label" style={{ gap: 0 }}>
          Available fields
        </span>
        {availableColumns.length ? (
          <div className="selection-list">
            {availableColumns.map((column) => (
              <div className="selection-row" key={column.value}>
                <div className="selection-row-copy" style={{ gridColumn: "1 / span 2" }}>
                  <span className="selection-row-title">{column.label}</span>
                  <span className="selection-row-description">Not shown in the saved table layout.</span>
                </div>
                <div className="selection-row-actions">
                  <button className="button-secondary" onClick={() => addColumn(column.value)} type="button">
                    Add
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="status-text">All supported fields are already visible.</p>
        )}
      </div>
      <label className="field-label">
        Chart Y axis
        <select className="field-input" {...register("chart_y_axis")}>
          {dashboardChartYAxisOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
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
