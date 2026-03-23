"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as echarts from "echarts";

import { getDashboardChartYAxisLabel, type DashboardChartYAxis } from "@/lib/dashboard-chart-options";
import type { SearchTimeSeriesResponse } from "@/lib/api/types";

type HoverSeriesGroup = {
  family: "spf" | "dkim" | "dmarc";
  label: string;
  values: Array<{ label: string; value: number }>;
};

type HoverSnapshot = {
  date: string;
  groups: HoverSeriesGroup[];
};

const seriesMeta = [
  { key: "spf_pass", family: "spf", label: "SPF pass", color: "#1f7a45" },
  { key: "spf_fail", family: "spf", label: "SPF fail", color: "#c0392b" },
  { key: "spf_unknown", family: "spf", label: "SPF unknown", color: "#5c6f87" },
  { key: "dkim_pass", family: "dkim", label: "DKIM pass", color: "#2c6db2" },
  { key: "dkim_fail", family: "dkim", label: "DKIM fail", color: "#8e2c22" },
  { key: "dkim_unknown", family: "dkim", label: "DKIM unknown", color: "#6c757d" },
  { key: "dmarc_pass", family: "dmarc", label: "DMARC pass", color: "#0f766e" },
  { key: "dmarc_fail", family: "dmarc", label: "DMARC fail", color: "#ba7e00" },
  { key: "dmarc_unknown", family: "dmarc", label: "DMARC unknown", color: "#7c8da6" },
] as const;

function clampIndex(index: number, maxIndex: number): number {
  return Math.max(0, Math.min(maxIndex, index));
}

function resolveZoomDate(
  value: string | number | undefined,
  dates: string[],
  fallbackPercent: number | undefined,
  mode: "start" | "end",
): string {
  if (!dates.length) {
    return "";
  }
  if (typeof value === "string" && dates.includes(value)) {
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    const numericIndex = clampIndex(Math.round(value), dates.length - 1);
    if (dates[numericIndex]) {
      return dates[numericIndex];
    }
  }
  if (typeof fallbackPercent === "number" && Number.isFinite(fallbackPercent)) {
    const scaledIndex = mode === "start" ? Math.floor((fallbackPercent / 100) * (dates.length - 1)) : Math.ceil((fallbackPercent / 100) * (dates.length - 1));
    return dates[clampIndex(scaledIndex, dates.length - 1)] ?? "";
  }
  return mode === "start" ? dates[0] ?? "" : dates[dates.length - 1] ?? "";
}

function resolveZoomRange(
  zoomState: Record<string, unknown> | null,
  dates: string[],
): { from: string; to: string } | null {
  if (!zoomState || !dates.length) {
    return null;
  }

  const startValue = zoomState.startValue;
  const endValue = zoomState.endValue;
  const startPercent = typeof zoomState.start === "number" ? zoomState.start : undefined;
  const endPercent = typeof zoomState.end === "number" ? zoomState.end : undefined;
  const from = resolveZoomDate(
    typeof startValue === "string" || typeof startValue === "number" ? startValue : undefined,
    dates,
    startPercent,
    "start",
  );
  const to = resolveZoomDate(
    typeof endValue === "string" || typeof endValue === "number" ? endValue : undefined,
    dates,
    endPercent,
    "end",
  );

  if (!from || !to) {
    return null;
  }
  return from <= to ? { from, to } : { from: to, to: from };
}

function isZoomCandidate(value: Record<string, unknown>): boolean {
  return (
    typeof value.start === "number" ||
    typeof value.end === "number" ||
    typeof value.startValue === "string" ||
    typeof value.startValue === "number" ||
    typeof value.endValue === "string" ||
    typeof value.endValue === "number"
  );
}

function extractZoomCandidates(params: unknown): Array<Record<string, unknown>> {
  const candidates: Array<Record<string, unknown>> = [];

  if (!params || typeof params !== "object") {
    return candidates;
  }

  if (Array.isArray((params as { batch?: unknown }).batch)) {
    (params as { batch: unknown[] }).batch.forEach((entry) => {
      if (entry && typeof entry === "object" && isZoomCandidate(entry as Record<string, unknown>)) {
        candidates.push(entry as Record<string, unknown>);
      }
    });
  }

  if (isZoomCandidate(params as Record<string, unknown>)) {
    candidates.push(params as Record<string, unknown>);
  }

  return candidates;
}

function buildHoverSnapshot(params: unknown): HoverSnapshot | null {
  if (!Array.isArray(params) || !params.length) {
    return null;
  }
  const date = String(params[0]?.axisValueLabel ?? params[0]?.axisValue ?? "");
  if (!date) {
    return null;
  }
  const valuesByFamily: Record<string, HoverSeriesGroup> = {
    spf: { family: "spf", label: "SPF", values: [] },
    dkim: { family: "dkim", label: "DKIM", values: [] },
    dmarc: { family: "dmarc", label: "DMARC", values: [] },
  };
  params.forEach((item) => {
    const name = String(item?.seriesName ?? "");
    const value = Array.isArray(item?.value) ? Number(item.value[1] ?? 0) : Number(item?.value ?? 0);
    const match = seriesMeta.find((entry) => entry.label === name);
    if (!match) {
      return;
    }
    const outcome = name.split(" ").slice(1).join(" ");
    valuesByFamily[match.family].values.push({ label: outcome, value: Number.isFinite(value) ? value : 0 });
  });
  return {
    date,
    groups: [valuesByFamily.spf, valuesByFamily.dkim, valuesByFamily.dmarc],
  };
}

function buildChartOption(
  data: SearchTimeSeriesResponse,
  yAxisLabel: string,
  onHoverSnapshot: (snapshot: HoverSnapshot | null) => void,
) {
  return {
    animation: false,
    grid: { top: 42, left: 42, right: 24, bottom: 56, containLabel: true },
    legend: {
      top: 0,
      left: "center",
      itemGap: 16,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (params: unknown) => {
        const snapshot = buildHoverSnapshot(params);
        onHoverSnapshot(snapshot);
        if (!snapshot) {
          return "";
        }
        return [
          `<strong>${snapshot.date}</strong>`,
          ...snapshot.groups.flatMap((group) => [
            `<div style="margin-top:6px;"><strong>${group.label}</strong></div>`,
            ...group.values.map((value) => `${value.label}: ${value.value}`),
          ]),
        ].join("<br/>");
      },
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: data.buckets.map((bucket) => bucket.date),
    },
    yAxis: {
      type: "value",
      name: yAxisLabel,
      nameLocation: "middle",
      nameGap: 58,
    },
    dataZoom: [
      { type: "inside", xAxisIndex: 0, filterMode: "none", realtime: false },
      { type: "slider", xAxisIndex: 0, filterMode: "none", realtime: false, height: 24, bottom: 16 },
    ],
    series: seriesMeta.map((series) => ({
      name: series.label,
      type: "line",
      showSymbol: false,
      smooth: true,
      lineStyle: { width: 2 },
      itemStyle: { color: series.color },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: `${series.color}66` },
          { offset: 1, color: `${series.color}12` },
        ]),
      },
      emphasis: { focus: "series" },
      data: data.buckets.map((bucket) => {
        const [family, outcome] = series.key.split("_");
        const valueSet = bucket[family as "spf" | "dkim" | "dmarc"];
        return [bucket.date, valueSet[outcome as "pass" | "fail" | "unknown"]];
      }),
    })),
  };
}

function TimeSeriesCanvas({
  className,
  data,
  from,
  onHoverSnapshot,
  onRangeSelect,
  to,
  yAxis,
}: {
  className: string;
  data: SearchTimeSeriesResponse;
  from: string;
  onHoverSnapshot: (snapshot: HoverSnapshot | null) => void;
  onRangeSelect: (from: string, to: string) => void;
  to: string;
  yAxis: DashboardChartYAxis;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.EChartsType | null>(null);
  const suppressRangeSyncRef = useRef(false);
  const lastCommittedRangeRef = useRef<{ from: string; to: string } | null>(null);
  const onHoverSnapshotRef = useRef(onHoverSnapshot);
  const onRangeSelectRef = useRef(onRangeSelect);
  const yAxisLabel = useMemo(() => getDashboardChartYAxisLabel(yAxis), [yAxis]);
  const chartDates = useMemo(() => data.buckets.map((bucket) => bucket.date), [data]);

  useEffect(() => {
    onHoverSnapshotRef.current = onHoverSnapshot;
  }, [onHoverSnapshot]);

  useEffect(() => {
    onRangeSelectRef.current = onRangeSelect;
  }, [onRangeSelect]);

  useEffect(() => {
    if (!containerRef.current) {
      return undefined;
    }
    const chart = echarts.init(containerRef.current, undefined, { renderer: "canvas" });
    chartRef.current = chart;
    const resizeObserver = new ResizeObserver(() => {
      chart.resize();
    });
    resizeObserver.observe(containerRef.current);

    const commitRange = (range: { from: string; to: string }) => {
      if (
        lastCommittedRangeRef.current?.from === range.from &&
        lastCommittedRangeRef.current?.to === range.to
      ) {
        return;
      }
      lastCommittedRangeRef.current = range;
      onRangeSelectRef.current(range.from, range.to);
    };

    chart.on("globalout", () => onHoverSnapshotRef.current(null));
    chart.on("datazoom", (params: unknown) => {
      if (!chartRef.current || suppressRangeSyncRef.current || !chartDates.length) {
        return;
      }
      const nextRange =
        extractZoomCandidates(params).reduce<{ from: string; to: string } | null>((selected, candidate) => {
          if (selected) {
            return selected;
          }
          return resolveZoomRange(candidate, chartDates);
        }, null) ?? null;
      if (!nextRange) {
        return;
      }
      commitRange(nextRange);
    });

    return () => {
      resizeObserver.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, [chartDates]);

  useEffect(() => {
    lastCommittedRangeRef.current = { from, to };
  }, [from, to]);

  useEffect(() => {
    if (!chartRef.current) {
      return;
    }
    const chart = chartRef.current;
    suppressRangeSyncRef.current = true;
    chart.setOption(buildChartOption(data, yAxisLabel, onHoverSnapshotRef.current), {
      notMerge: false,
      lazyUpdate: true,
      replaceMerge: ["series", "xAxis", "yAxis", "dataZoom"],
    });
    if (chartDates.length) {
      chart.dispatchAction({
        type: "dataZoom",
        startValue: from || chartDates[0],
        endValue: to || chartDates[chartDates.length - 1],
      });
    }
    window.requestAnimationFrame(() => {
      suppressRangeSyncRef.current = false;
    });
  }, [chartDates, data, from, to, yAxisLabel]);

  return <div aria-label="Dashboard trend chart" className={className} ref={containerRef} role="img" />;
}

export function DashboardTimeSeriesChart({
  data,
  error,
  from,
  isFetching,
  isLoading,
  onRangeSelect,
  to,
  yAxis,
}: {
  data?: SearchTimeSeriesResponse;
  error?: string | null;
  from: string;
  isFetching: boolean;
  isLoading: boolean;
  onRangeSelect: (from: string, to: string) => void;
  to: string;
  yAxis: DashboardChartYAxis;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [hoverSnapshot, setHoverSnapshot] = useState<HoverSnapshot | null>(null);
  const [lastSuccessfulData, setLastSuccessfulData] = useState<SearchTimeSeriesResponse | undefined>(
    data?.buckets.length ? data : undefined,
  );

  useEffect(() => {
    if (data?.buckets.length) {
      setLastSuccessfulData(data);
      return;
    }
    if (!isFetching && data && !data.buckets.length) {
      setLastSuccessfulData(undefined);
    }
  }, [data, isFetching]);

  const visibleData = data?.buckets.length ? data : isFetching ? lastSuccessfulData : undefined;
  const showEmptyState = !isLoading && !isFetching && !error && !!data && !data.buckets.length;

  return (
    <>
      <section className="surface-card stack">
        <div className="section-heading">
          <div className="stack" style={{ gap: 6 }}>
            <h2 className="section-title">Trend</h2>
            <p className="section-intro">Time-based summary of SPF, DKIM, and DMARC outcomes for the current dashboard scope.</p>
          </div>
          <button className="button-secondary" disabled={!visibleData?.buckets.length} onClick={() => setIsExpanded(true)} type="button">
            Expand
          </button>
        </div>
        {isLoading || isFetching ? <p className="status-text">Loading chart data...</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
        {showEmptyState ? (
          <p className="status-text">No chart data yet for the current dashboard filters.</p>
        ) : null}
        {visibleData?.buckets.length ? (
          <TimeSeriesCanvas
            className="dashboard-chart-canvas"
            data={visibleData}
            from={from}
            onHoverSnapshot={setHoverSnapshot}
            onRangeSelect={onRangeSelect}
            to={to}
            yAxis={yAxis}
          />
        ) : null}
      </section>
      {isExpanded && visibleData?.buckets.length ? (
        <div className="modal-backdrop" onClick={() => setIsExpanded(false)} role="presentation">
          <div
            aria-modal="true"
            className="modal-card surface-card chart-modal-card"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
          >
            <div className="modal-header">
              <div className="stack" style={{ gap: 8 }}>
                <p className="eyebrow">Visualization</p>
                <h2 style={{ margin: 0 }}>Trend</h2>
                <p className="status-text" style={{ margin: 0 }}>
                  Drag the chart range to update the dashboard time filter and hover to inspect per-series values.
                </p>
              </div>
              <button aria-label="Close chart" className="icon-button" onClick={() => setIsExpanded(false)} type="button">
                ×
              </button>
            </div>
            <div className="chart-modal-layout">
              <TimeSeriesCanvas
                className="dashboard-chart-canvas dashboard-chart-canvas-expanded"
                data={visibleData}
                from={from}
                onHoverSnapshot={setHoverSnapshot}
                onRangeSelect={onRangeSelect}
                to={to}
                yAxis={yAxis}
              />
              <div className="chart-hover-panel">
                <p className="stat-label">Hovered point</p>
                {hoverSnapshot ? (
                  <div className="chart-hover-card-grid">
                    <article className="detail-card detail-card-wide">
                      <p className="stat-label">Date</p>
                      <strong>{hoverSnapshot.date}</strong>
                    </article>
                    {hoverSnapshot.groups.map((group) => (
                      <article className="detail-card" key={group.family}>
                        <p className="stat-label">{group.label}</p>
                        <div className="stack" style={{ gap: 6 }}>
                          {group.values.map((value) => (
                            <span key={value.label}>
                              <strong>{value.label}</strong>: {value.value}
                            </span>
                          ))}
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="status-text">Hover any point in the chart to inspect the values for that date.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
