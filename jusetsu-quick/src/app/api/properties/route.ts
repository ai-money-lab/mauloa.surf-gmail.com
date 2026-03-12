import { NextRequest, NextResponse } from "next/server";
import { getStore } from "@/lib/store";
import type { StoredProperty } from "@/lib/store";

export const runtime = "edge";

export async function GET() {
  const store = getStore();
  const results = Array.from(store.values()).sort(
    (a, b) => (b.updated_at || "").localeCompare(a.updated_at || "")
  );
  return NextResponse.json({ results });
}

export async function POST(req: NextRequest) {
  const store = getStore();

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
  const now = new Date().toISOString();

  const property: StoredProperty = {
    id,
    company_id: (data.company_id as string) || "demo",
    created_by: (data.created_by as string) || "demo",
    address: data.address as string,
    property_type: (data.property_type as string) || "condo",
    status: (data.status as string) || "draft",
    created_at: now,
    updated_at: now,
  };

  // Copy all known PropertyData fields
  const knownFields = [
    "latitude", "longitude", "zoning", "building_coverage_ratio", "floor_area_ratio",
    "fire_zone", "urban_plan_zone", "height_district", "flood_level", "flood_text",
    "flood_river", "tsunami_level", "tsunami_text", "hightide_level", "hightide_text",
    "sediment_risk", "landslide_text", "school_district", "school_district_jr",
    "land_price", "land_price_year", "land_price_point", "future_pop", "future_pop_2050",
    "future_pop_change", "api_fetched_at", "water_supply", "sewage", "gas_type",
    "electricity", "road_type", "road_width", "road_frontage", "private_road",
    "owner_name", "land_area", "building_area", "mortgage", "mgmt_fee", "repair_reserve",
    "parking_fee", "mgmt_form", "mgmt_company", "total_units", "major_repair_plan",
    "is_incident", "incident_detail", "disclosure_notes", "asbestos",
    "earthquake_resistance", "price", "transaction_type", "earnest_money",
    "delivery_date", "special_terms",
  ];

  for (const key of knownFields) {
    if (data[key] !== undefined) {
      (property as unknown as Record<string, unknown>)[key] = data[key];
    }
  }

  store.set(id, property);
  return NextResponse.json(property, { status: 201 });
}
