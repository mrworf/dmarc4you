import { NextResponse } from "next/server";
import { buildFrontendReadyPayload } from "@/lib/runtime-env";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(
    buildFrontendReadyPayload(),
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
