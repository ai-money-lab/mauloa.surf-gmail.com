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
  flood_level INTEGER DEFAULT 0,
  tsunami_level INTEGER DEFAULT 0,
  hightide_level INTEGER DEFAULT 0,
  sediment_risk INTEGER DEFAULT 0,
  school_district TEXT,
  land_price INTEGER,
  future_pop_trend REAL,
  api_raw_json TEXT,

  -- 手入力項目 - 登記情報
  owner_name TEXT,
  registry_area REAL,
  rights_type TEXT,
  mortgage_holder TEXT,
  mortgage_amount INTEGER,

  -- インフラ
  water_supply TEXT,
  sewage TEXT,
  gas_type TEXT,
  water_pipe_mm INTEGER,

  -- 道路
  road_type TEXT,
  road_width REAL,
  road_direction TEXT,

  -- マンション固有
  mgmt_fee INTEGER,
  repair_reserve INTEGER,
  mgmt_company TEXT,
  total_units INTEGER,
  building_age INTEGER,
  floor_number TEXT,

  -- 告知事項
  disclosure_notes TEXT,
  is_incident INTEGER DEFAULT 0,
  asbestos TEXT,
  earthquake_resistance TEXT,

  -- 契約条件
  price INTEGER,
  transaction_type TEXT,
  earnest_money INTEGER,

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
