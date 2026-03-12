import type { PropertyData } from "./types";

export interface StoredProperty extends PropertyData {
  id: string;
  company_id: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

// Use globalThis to persist across HMR in dev mode
// In production, replace with D1 database
const globalRef = globalThis as unknown as {
  __jusetsuStore?: Map<string, StoredProperty>;
};

if (!globalRef.__jusetsuStore) {
  globalRef.__jusetsuStore = new Map<string, StoredProperty>();
}

export function getStore() {
  return globalRef.__jusetsuStore!;
}
