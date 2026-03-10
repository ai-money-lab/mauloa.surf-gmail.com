import type { PropertyData } from "./types";

export interface StoredProperty extends PropertyData {
  id: string;
  company_id: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

// Singleton in-memory store shared across all API routes
// In production, replace with D1 database
const store = new Map<string, StoredProperty>();

export function getStore() {
  return store;
}
