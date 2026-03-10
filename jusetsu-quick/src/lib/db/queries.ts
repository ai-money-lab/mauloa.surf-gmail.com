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

export async function createProperty(
  db: D1Database,
  data: {
    id: string;
    company_id: string;
    created_by: string;
    address: string;
    latitude: number;
    longitude: number;
    property_type: string;
    zoning?: string;
    building_coverage_ratio?: number;
    floor_area_ratio?: number;
    fire_zone?: string;
    urban_plan_zone?: string;
    flood_level?: number;
    tsunami_level?: number;
    hightide_level?: number;
    sediment_risk?: number;
    school_district?: string;
    land_price?: number;
    api_raw_json?: string;
  }
) {
  return db
    .prepare(
      `INSERT INTO properties (
      id, company_id, created_by, address, latitude, longitude, property_type,
      api_fetched_at, zoning, building_coverage_ratio, floor_area_ratio,
      fire_zone, urban_plan_zone, flood_level, tsunami_level, hightide_level,
      sediment_risk, school_district, land_price, api_raw_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
    )
    .bind(
      data.id,
      data.company_id,
      data.created_by,
      data.address,
      data.latitude,
      data.longitude,
      data.property_type,
      data.zoning || null,
      data.building_coverage_ratio || null,
      data.floor_area_ratio || null,
      data.fire_zone || null,
      data.urban_plan_zone || null,
      data.flood_level || 0,
      data.tsunami_level || 0,
      data.hightide_level || 0,
      data.sediment_risk || 0,
      data.school_district || null,
      data.land_price || null,
      data.api_raw_json || null
    )
    .run();
}

export async function updatePropertyManual(
  db: D1Database,
  id: string,
  data: Record<string, unknown>
) {
  const fields = Object.keys(data).filter((k) => data[k] !== undefined);
  if (fields.length === 0) return;
  const setClauses = fields.map((f) => `${f} = ?`).join(", ");
  const values = fields.map((f) => data[f]);
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
  companyId: string,
  limit = 50
) {
  return db
    .prepare(
      "SELECT id, address, property_type, status, created_at, updated_at FROM properties WHERE company_id = ? ORDER BY updated_at DESC LIMIT ?"
    )
    .bind(companyId, limit)
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
