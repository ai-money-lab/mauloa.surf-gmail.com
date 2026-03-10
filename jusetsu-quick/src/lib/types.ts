export interface PropertyData {
  id?: string;
  address: string;
  latitude?: number;
  longitude?: number;
  property_type: string;

  // API自動取得
  zoning?: string;
  building_coverage_ratio?: number;
  floor_area_ratio?: number;
  fire_zone?: string;
  urban_plan_zone?: string;
  height_district?: string;
  flood_level?: number;
  flood_text?: string;
  flood_river?: string;
  tsunami_level?: number;
  tsunami_text?: string;
  hightide_level?: number;
  hightide_text?: string;
  sediment_risk?: number;
  landslide_text?: string;
  school_district?: string;
  school_district_jr?: string;
  land_price?: number;
  land_price_year?: number;
  land_price_point?: string;
  future_pop?: number;
  future_pop_2050?: number;
  future_pop_change?: number;
  api_fetched_at?: string;

  // 手入力 - インフラ
  water_supply?: string;
  sewage?: string;
  gas_type?: string;
  electricity?: string;

  // 道路
  road_type?: string;
  road_width?: string;
  road_frontage?: string;
  private_road?: string;

  // 登記
  owner_name?: string;
  land_area?: string;
  building_area?: string;
  mortgage?: string;

  // マンション
  mgmt_fee?: string;
  repair_reserve?: string;
  parking_fee?: string;
  mgmt_form?: string;
  mgmt_company?: string;
  total_units?: string;
  major_repair_plan?: string;

  // 告知
  is_incident?: boolean;
  incident_detail?: string;
  disclosure_notes?: string;
  asbestos?: string;
  earthquake_resistance?: string;

  // 契約
  price?: string;
  transaction_type?: string;
  earnest_money?: string;
  delivery_date?: string;
  special_terms?: string;

  status?: string;
}

export interface SearchResult {
  lat: number;
  lng: number;
  zoning?: string;
  building_coverage_ratio?: number;
  floor_area_ratio?: number;
  fire_zone?: string;
  height_district?: string;
  urban_plan_zone?: string;
  flood_level?: number;
  flood_text?: string;
  flood_river?: string;
  tsunami_level?: number;
  tsunami_text?: string;
  hightide_level?: number;
  hightide_text?: string;
  landslide_text?: string;
  sediment_risk?: number;
  school_district?: string;
  school_district_jr?: string;
  land_price?: number;
  land_price_year?: number;
  land_price_point?: string;
  future_pop?: number;
  future_pop_2050?: number;
  future_pop_change?: number;
  elapsed_ms?: number;
}
