-- デモ会社・ユーザーを挿入（FOREIGN KEY制約を満たすため）
INSERT OR IGNORE INTO companies (id, name) VALUES ('demo', 'デモ会社');
INSERT OR IGNORE INTO users (id, company_id, email, name, role)
  VALUES ('demo', 'demo', 'demo@example.com', 'デモユーザー', 'admin');
