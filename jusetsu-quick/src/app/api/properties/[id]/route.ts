import { NextRequest, NextResponse } from "next/server";

// Shared in-memory store reference (same pattern as parent route for MVP)
// In production, this would use D1 database
const store: Record<string, Record<string, unknown>> = {};

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const property = store[params.id];
  if (!property) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json(property);
}

export async function PUT(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const existing = store[params.id];
  if (!existing) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  const data = await req.json();
  store[params.id] = {
    ...existing,
    ...data,
    updated_at: new Date().toISOString(),
  };
  return NextResponse.json(store[params.id]);
}
