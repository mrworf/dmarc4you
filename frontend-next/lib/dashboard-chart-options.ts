export const dashboardChartYAxisOptions = [
  { value: "message_count", label: "Message count" },
  { value: "row_count", label: "Row count" },
  { value: "report_count", label: "Report count" },
] as const;

export type DashboardChartYAxis = (typeof dashboardChartYAxisOptions)[number]["value"];

export const defaultDashboardChartYAxis: DashboardChartYAxis = "message_count";

export function getDashboardChartYAxisLabel(value: DashboardChartYAxis | string): string {
  return dashboardChartYAxisOptions.find((option) => option.value === value)?.label ?? "Message count";
}
