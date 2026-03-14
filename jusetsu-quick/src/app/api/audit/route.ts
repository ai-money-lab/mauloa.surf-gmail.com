import { NextRequest, NextResponse } from "next/server";
import { getRequestContext } from "@cloudflare/next-on-pages";
import { getAuditLogs } from "@/lib/db/queries";
import { ensureSchema } from "@/lib/db/ensure-schema";

export const runtime = "edge";

export async function GET(req: NextRequest) {
  try {
    const { env } = getRequestContext();
    const db = env.DB;
    await ensureSchema(db);

    const propertyId = req.nextUrl.searchParams.get("property_id") || undefined;
    const limit = parseInt(req.nextUrl.searchParams.get("limit") || "50", 10);

    const { results } = await getAuditLogs(db, propertyId, limit);
    return NextResponse.json({ results });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
