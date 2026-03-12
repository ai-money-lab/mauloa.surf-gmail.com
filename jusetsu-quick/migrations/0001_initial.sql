-- 会社（テナント）
CREATE TABLE IF NOT EXISTS companies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  license_number TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

-- ユーザー
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

-- 物件（重説の核心データ）
CREATE TABLE IF NOT EXISTS properties (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  created_by TEXT NOT NULL,

  -- 基本情報
  address TEXT NOT NULL,
  latitude REAL,
  longitude REAL,
  property_type TEXT DEFAULT 'condo',

  -- API自動取得項目
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

  -- 手入力項目 - インフラ
  water_supply TEXT,
  sewage TEXT,
  gas_type TEXT,
  electricity TEXT,

  -- 道路
  road_type TEXT,
  road_width TEXT,
  road_frontage TEXT,
  private_road TEXT,

  -- 登記情報
  owner_name TEXT,
  land_area TEXT,
  building_area TEXT,
  mortgage TEXT,

  -- マンション固有
  mgmt_fee TEXT,
  repair_reserve TEXT,
  parking_fee TEXT,
  mgmt_form TEXT,
  mgmt_company TEXT,
  total_units TEXT,
  major_repair_plan TEXT,

  -- 告知事項
  is_incident INTEGER DEFAULT 0,
  incident_detail TEXT,
  disclosure_notes TEXT,
  asbestos TEXT,
  earthquake_resistance TEXT,

  -- 契約条件
  price TEXT,
  transaction_type TEXT,
  earnest_money TEXT,
  delivery_date TEXT,
  special_terms TEXT,

  -- ステータス
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

-- 統計集計用テーブル（将来のデータ販売用）
CREATE TABLE IF NOT EXISTS area_stats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  area_code TEXT,
  property_type TEXT,
  avg_mgmt_fee INTEGER,
  avg_repair_reserve INTEGER,
  avg_price_sqm INTEGER,
  sample_count INTEGER,
  period TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);
