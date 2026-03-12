import { NextRequest, NextResponse } from "next/server";
import { getRequestContext } from "@cloudflare/next-on-pages";
import { createProperty, listProperties } from "@/lib/db/queries";

export const runtime = "edge";

export async function GET() {
  try {
    const { env } = getRequestContext();
    const db = env.DB;
    const { results } = await listProperties(db);
    return NextResponse.json({ results });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("GET /api/properties failed:", msg);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  let data: Record<string, unknown>;
  try {
    data = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (!data.address || typeof data.address !== "string") {
    return NextResponse.json({ error: "address is required" }, { status: 400 });
  }

  let env;
  try {
    env = getRequestContext().env;
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("getRequestContext failed:", msg);
    return NextResponse.json({ error: `Runtime error: ${msg}` }, { status: 500 });
  }

  const db = env.DB;
  if (!db) {
    return NextResponse.json({ error: "Database not configured (DB binding missing)" }, { status: 500 });
  }

  const id =
    (typeof data.id === "string" && data.id) ||
    crypto.randomUUID().replace(/-/g, "").slice(0, 16);

  const property = {
    ...data,
    id,
    company_id: (data.company_id as string) || "demo",
    created_by: (data.created_by as string) || "demo",
    address: data.address as string,
    property_type: (data.property_type as string) || "condo",
    status: (data.status as string) || "draft",
  };

  try {
    await createProperty(db, property as Record<string, unknown> & {
      id: string;
      company_id: string;
      created_by: string;
      address: string;
    });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("createProperty failed:", msg, JSON.stringify(data).slice(0, 500));
    return NextResponse.json({ error: `DB保存エラー: ${msg}` }, { status: 500 });
  }

  try {
    const created = await db
      .prepare("SELECT * FROM properties WHERE id = ?")
      .bind(id)
      .first();
    return NextResponse.json(created, { status: 201 });
  } catch {
    // Insert succeeded but SELECT failed - still return success
    return NextResponse.json({ id }, { status: 201 });
  }
}
