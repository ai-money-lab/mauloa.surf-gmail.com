export function generateId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 16);
}

interface D1Database {
  prepare(sql: string): D1PreparedStatement;
}

interface D1PreparedStatement {
  bind(...values: unknown[]): D1PreparedStatement;
  run(): Promise<unknown>;
  first(): Promise<Record<string, unknown> | null>;
  all(): Promise<{ results: Record<string, unknown>[] }>;
}

// All property columns (excluding id, company_id, created_by, created_at, updated_at)
const PROPERTY_COLUMNS = [
  "address", "latitude", "longitude", "property_type",
  "api_fetched_at", "zoning", "building_coverage_ratio", "floor_area_ratio",
  "fire_zone", "urban_plan_zone", "height_district",
  "flood_level", "flood_text", "flood_river",
  "tsunami_level", "tsunami_text",
  "hightide_level", "hightide_text",
  "sediment_risk", "landslide_text",
  "school_district", "school_district_jr",
  "land_price", "land_price_year", "land_price_point",
  "future_pop", "future_pop_2050", "future_pop_change",
  "api_raw_json",
  "water_supply", "sewage", "gas_type", "electricity",
  "road_type", "road_width", "road_frontage", "private_road",
  "owner_name", "land_area", "building_area", "mortgage",
  "mgmt_fee", "repair_reserve", "parking_fee", "mgmt_form",
  "mgmt_company", "total_units", "major_repair_plan",
  "is_incident", "incident_detail", "disclosure_notes",
  "asbestos", "earthquake_resistance",
  "price", "transaction_type", "earnest_money",
  "delivery_date", "special_terms",
  "rent", "common_area_fee", "deposit_months", "key_money_months",
  "lease_start", "lease_end", "lease_term_years", "lease_type",
  "rent_payment_method", "rent_payment_due", "renewal_fee",
  "purpose_of_use", "pet_allowed", "smoking_allowed", "sublease_allowed",
  "restoration_terms", "cancellation_notice",
  "guarantor_required", "guarantee_company", "fire_insurance",
  "status",
] as const;

const ALLOWED_COLS = new Set<string>(PROPERTY_COLUMNS);

/**
 * Sanitize a value for D1/SQLite binding.
 * D1 only accepts: string, number, null, ArrayBuffer.
 * Booleans → 0/1, objects → JSON string, undefined → null.
 */
function sanitizeValue(val: unknown): string | number | null {
  if (val === null || val === undefined) return null;
  if (typeof val === "boolean") return val ? 1 : 0;
  if (typeof val === "number") return isFinite(val) ? val : null;
  if (typeof val === "string") return val;
  // Objects/arrays → JSON string
  try { return JSON.stringify(val); } catch { return null; }
}

export async function createProperty(
  db: D1Database,
  data: Record<string, unknown> & {
    id: string;
    company_id: string;
    created_by: string;
    address: string;
  }
) {
  const columns = ["id", "company_id", "created_by"];
  const values: (string | number | null)[] = [data.id, data.company_id, data.created_by];

  for (const col of PROPERTY_COLUMNS) {
    if (data[col] !== undefined) {
      columns.push(col);
      values.push(sanitizeValue(data[col]));
    }
  }

  const placeholders = columns.map(() => "?").join(", ");
  return db
    .prepare(
      `INSERT INTO properties (${columns.join(", ")}) VALUES (${placeholders})`
    )
    .bind(...values)
    .run();
}

export async function updatePropertyManual(
  db: D1Database,
  id: string,
  data: Record<string, unknown>
) {
  const fields = Object.keys(data).filter(
    (k) => data[k] !== undefined && ALLOWED_COLS.has(k)
  );
  if (fields.length === 0) return;

  const setClauses = fields.map((f) => `${f} = ?`).join(", ");
  const values = fields.map((f) => sanitizeValue(data[f]));

  return db
    .prepare(
      `UPDATE properties SET ${setClauses}, updated_at = datetime('now') WHERE id = ?`
    )
    .bind(...values, id)
    .run();
}

export async function getProperty(db: D1Database, id: string) {
  return db.prepare("SELECT * FROM properties WHERE id = ?").bind(id).first();
}

export async function listProperties(
  db: D1Database,
  companyId?: string,
  limit = 50
) {
  if (companyId) {
    return db
      .prepare(
        "SELECT * FROM properties WHERE company_id = ? ORDER BY updated_at DESC LIMIT ?"
      )
      .bind(companyId, limit)
      .all();
  }
  return db
    .prepare("SELECT * FROM properties ORDER BY updated_at DESC LIMIT ?")
    .bind(limit)
    .all();
}

export async function findSameBuilding(
  db: D1Database,
  address: string,
  excludeId?: string
) {
  const baseAddress = address
    .replace(/\d+号室?$/, "")
    .replace(/\d+-\d+$/, "")
    .trim();
  if (excludeId) {
    return db
      .prepare(
        "SELECT id, address, mgmt_fee, repair_reserve, mgmt_company, total_units FROM properties WHERE address LIKE ? AND id != ? LIMIT 5"
      )
      .bind(`${baseAddress}%`, excludeId)
      .all();
  }
  return db
    .prepare(
      "SELECT id, address, mgmt_fee, repair_reserve, mgmt_company, total_units FROM properties WHERE address LIKE ? LIMIT 5"
    )
    .bind(`${baseAddress}%`)
    .all();
}
