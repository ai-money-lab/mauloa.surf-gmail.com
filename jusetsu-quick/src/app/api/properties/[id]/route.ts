import { NextRequest, NextResponse } from "next/server";
import { getStore } from "@/lib/store";

export const runtime = "edge";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const store = getStore();
  const property = store.get(id);
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
  const store = getStore();
  const existing = store.get(id);
  if (!existing) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  let data: Record<string, unknown>;
  try {
    data = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const updated = {
    ...existing,
    ...data,
    id: existing.id,
    created_at: existing.created_at,
    updated_at: new Date().toISOString(),
  };
  store.set(id, updated);
  return NextResponse.json(updated);
}
