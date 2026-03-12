/**
 * DBセルフヒーリング: テーブルとデモデータを自動作成
 * マイグレーション未適用でもAPIが動作するようにする
 */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type D1DB = any;

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS companies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  license_number TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  role TEXT DEFAULT 'member',
  session_token TEXT,
  session_expires TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  last_login TEXT,
  FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS properties (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  created_by TEXT NOT NULL,
  address TEXT NOT NULL,
  latitude REAL,
  longitude REAL,
  property_type TEXT DEFAULT 'condo',
  api_fetched_at TEXT,
  zoning TEXT,
  building_coverage_ratio REAL,
  floor_area_ratio REAL,
  fire_zone TEXT,
  urban_plan_zone TEXT,
  height_district TEXT,
  flood_level INTEGER DEFAULT 0,
  flood_text TEXT,
  flood_river TEXT,
  tsunami_level INTEGER DEFAULT 0,
  tsunami_text TEXT,
  hightide_level INTEGER DEFAULT 0,
  hightide_text TEXT,
  sediment_risk INTEGER DEFAULT 0,
  landslide_text TEXT,
  school_district TEXT,
  school_district_jr TEXT,
  land_price INTEGER,
  land_price_year INTEGER,
  land_price_point TEXT,
  future_pop REAL,
  future_pop_2050 REAL,
  future_pop_change REAL,
  api_raw_json TEXT,
  water_supply TEXT,
  sewage TEXT,
  gas_type TEXT,
  electricity TEXT,
  road_type TEXT,
  road_width TEXT,
  road_frontage TEXT,
  private_road TEXT,
  owner_name TEXT,
  land_area TEXT,
  building_area TEXT,
  mortgage TEXT,
  mgmt_fee TEXT,
  repair_reserve TEXT,
  parking_fee TEXT,
  mgmt_form TEXT,
  mgmt_company TEXT,
  total_units TEXT,
  major_repair_plan TEXT,
  is_incident INTEGER DEFAULT 0,
  incident_detail TEXT,
  disclosure_notes TEXT,
  asbestos TEXT,
  earthquake_resistance TEXT,
  price TEXT,
  transaction_type TEXT,
  earnest_money TEXT,
  delivery_date TEXT,
  special_terms TEXT,
  rent TEXT,
  common_area_fee TEXT,
  deposit_months TEXT,
  key_money_months TEXT,
  lease_start TEXT,
  lease_end TEXT,
  lease_term_years TEXT,
  lease_type TEXT,
  rent_payment_method TEXT,
  rent_payment_due TEXT,
  renewal_fee TEXT,
  purpose_of_use TEXT,
  pet_allowed TEXT,
  smoking_allowed TEXT,
  sublease_allowed TEXT,
  restoration_terms TEXT,
  cancellation_notice TEXT,
  guarantor_required TEXT,
  guarantee_company TEXT,
  fire_insurance TEXT,
  status TEXT DEFAULT 'draft',
  completed_at TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (company_id) REFERENCES companies(id),
  FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_prop_company ON properties(company_id);
CREATE INDEX IF NOT EXISTS idx_prop_address ON properties(address);
CREATE INDEX IF NOT EXISTS idx_prop_status ON properties(status);
`;

const SEED_SQL = `
INSERT OR IGNORE INTO companies (id, name) VALUES ('demo', 'デモ会社');
INSERT OR IGNORE INTO users (id, company_id, email, name, role) VALUES ('demo', 'demo', 'demo@example.com', 'デモユーザー', 'admin');
`;

// Cache: only run once per worker instance
let ensured = false;

export async function ensureSchema(db: D1DB): Promise<void> {
  if (ensured) return;
  try {
    // Quick check: if properties table exists, skip
    await db.prepare("SELECT 1 FROM properties LIMIT 1").bind().run();
    ensured = true;
    return;
  } catch {
    // Table doesn't exist, create everything
  }

  try {
    await db.exec(SCHEMA_SQL);
    await db.exec(SEED_SQL);
    ensured = true;
  } catch (e) {
    console.error("ensureSchema failed:", e);
    // Don't throw - let the actual query fail with a better error
  }
}
