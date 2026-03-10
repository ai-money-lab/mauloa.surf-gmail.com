import { NextRequest, NextResponse } from "next/server";

// MVP: In-memory store (replace with D1 in production)
const store: Record<string, Record<string, unknown>> = {};

export async function GET() {
  const results = Object.values(store).sort(
    (a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || ""))
  );
  return NextResponse.json({ results });
}

export async function POST(req: NextRequest) {
  const data = await req.json();
  const id = data.id || crypto.randomUUID().replace(/-/g, "").slice(0, 16);
  const now = new Date().toISOString();

  store[id] = {
    id,
    company_id: data.company_id || "demo",
    created_by: data.created_by || "demo",
    address: data.address,
    latitude: data.latitude,
    longitude: data.longitude,
    property_type: data.property_type || "condo",
    status: "draft",
    created_at: now,
    updated_at: now,
    ...data,
  };

  return NextResponse.json(store[id], { status: 201 });
}
