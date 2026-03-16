-- 監査ログテーブル（電子帳簿保存法対応）
CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  property_id TEXT,
  user_id TEXT DEFAULT 'demo',
  action TEXT NOT NULL,
  details TEXT,
  ip_address TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_property ON audit_logs(property_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);

-- 賃貸関連カラムの追加（ensure-schemaとの整合性）
ALTER TABLE properties ADD COLUMN rent TEXT;
ALTER TABLE properties ADD COLUMN common_area_fee TEXT;
ALTER TABLE properties ADD COLUMN deposit_months TEXT;
ALTER TABLE properties ADD COLUMN key_money_months TEXT;
ALTER TABLE properties ADD COLUMN lease_start TEXT;
ALTER TABLE properties ADD COLUMN lease_end TEXT;
ALTER TABLE properties ADD COLUMN lease_term_years TEXT;
ALTER TABLE properties ADD COLUMN lease_type TEXT;
ALTER TABLE properties ADD COLUMN rent_payment_method TEXT;
ALTER TABLE properties ADD COLUMN rent_payment_due TEXT;
ALTER TABLE properties ADD COLUMN renewal_fee TEXT;
ALTER TABLE properties ADD COLUMN purpose_of_use TEXT;
ALTER TABLE properties ADD COLUMN pet_allowed TEXT;
ALTER TABLE properties ADD COLUMN smoking_allowed TEXT;
ALTER TABLE properties ADD COLUMN sublease_allowed TEXT;
ALTER TABLE properties ADD COLUMN restoration_terms TEXT;
ALTER TABLE properties ADD COLUMN cancellation_notice TEXT;
ALTER TABLE properties ADD COLUMN guarantor_required TEXT;
ALTER TABLE properties ADD COLUMN guarantee_company TEXT;
ALTER TABLE properties ADD COLUMN fire_insurance TEXT;
