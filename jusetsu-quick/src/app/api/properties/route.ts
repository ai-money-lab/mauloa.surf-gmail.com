import { NextRequest, NextResponse } from "next/server";
import { getRequestContext } from "@cloudflare/next-on-pages";
import { createProperty, listProperties } from "@/lib/db/queries";

export const runtime = "edge";

export async function GET() {
  const { env } = getRequestContext();
  const db = env.DB;

  const { results } = await listProperties(db);
  return NextResponse.json({ results });
}

export async function POST(req: NextRequest) {
  const { env } = getRequestContext();
  const db = env.DB;

  let data: Record<string, unknown>;
  try {
    data = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (!data.address || typeof data.address !== "string") {
    return NextResponse.json({ error: "address is required" }, { status: 400 });
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

  await createProperty(db, property as Record<string, unknown> & {
    id: string;
    company_id: string;
    created_by: string;
    address: string;
  });

  // Return the created property with timestamps
  const created = await db
    .prepare("SELECT * FROM properties WHERE id = ?")
    .bind(id)
    .first();

  return NextResponse.json(created, { status: 201 });
}
