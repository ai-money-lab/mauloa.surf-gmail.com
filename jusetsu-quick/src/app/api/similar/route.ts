import { NextRequest, NextResponse } from "next/server";
import { getRequestContext } from "@cloudflare/next-on-pages";
import { findSameBuilding } from "@/lib/db/queries";

export const runtime = "edge";

export async function GET(req: NextRequest) {
  const address = req.nextUrl.searchParams.get("address");
  if (!address) {
    return NextResponse.json({ error: "address is required" }, { status: 400 });
  }

  const { env } = getRequestContext();
  const db = env.DB;

  const excludeId = req.nextUrl.searchParams.get("exclude") || undefined;
  const { results } = await findSameBuilding(db, address, excludeId);

  return NextResponse.json({ results });
}
