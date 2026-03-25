import { NextResponse } from "next/server";

function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";
}

export async function GET() {
  return NextResponse.json(
    {
      status: "ok",
      service: "frontend-next",
      frontend: {
        mode: getApiBaseUrl() ? "split-origin" : "same-origin",
      },
      backend: {
        apiBaseUrl: getApiBaseUrl() || "same-origin",
        readinessPath: "/api/v1/health/ready",
        sourceOfTruth: "fastapi",
      },
      operations: {
        webRole: "Next.js frontend",
        workerRole: "FastAPI background jobs and workers",
      },
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
