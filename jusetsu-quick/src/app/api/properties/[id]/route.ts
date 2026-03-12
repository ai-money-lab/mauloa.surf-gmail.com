import { NextRequest, NextResponse } from "next/server";
import { getRequestContext } from "@cloudflare/next-on-pages";
import { getProperty, updatePropertyManual } from "@/lib/db/queries";

export const runtime = "edge";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { env } = getRequestContext();
  const db = env.DB;

  const property = await getProperty(db, id);
  if (!property) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json(property);
}

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { env } = getRequestContext();
  const db = env.DB;

  const existing = await getProperty(db, id);
  if (!existing) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  let data: Record<string, unknown>;
  try {
    data = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  // Remove fields that should not be updated directly
  delete data.id;
  delete data.created_at;

  await updatePropertyManual(db, id, data);

  const updated = await getProperty(db, id);
  return NextResponse.json(updated);
}
