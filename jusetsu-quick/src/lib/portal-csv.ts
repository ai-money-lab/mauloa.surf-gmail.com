/**
 * ポータルサイト一括入稿CSV生成
 * SUUMO / HOME'S 形式の CSV を PropertyData から自動生成
 */
import type { PropertyData } from "./types";

const BOM = "\uFEFF";

/** CSV injection safe escape */
function esc(s: string): string {
  const v = s.replace(/"/g, '""');
  // Block formula injection
  const dangerous = /^[=+\-@\t\r]/.test(v);
  return dangerous ? `"'${v}"` : `"${v}"`;
}

function row(cells: string[]): string {
  return cells.map(esc).join(",");
}

function download(filename: string, csvContent: string) {
  const blob = new Blob([BOM + csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** 住所から都道府県・市区町村・町名以降を分割 */
function splitAddress(address: string): { pref: string; city: string; town: string } {
  const prefMatch = address.match(/^(.{2,3}[都道府県])/);
  const pref = prefMatch ? prefMatch[1] : "";
  const rest = pref ? address.slice(pref.length) : address;
  const cityMatch = rest.match(/^(.+?[市区町村郡])/);
  const city = cityMatch ? cityMatch[1] : "";
  const town = city ? rest.slice(city.length) : rest;
  return { pref, city, town };
}

/** 物件種別をポータル用の文字列に変換 */
function portalPropertyType(type: string, isRental: boolean): string {
  if (isRental) {
    if (type === "mansion") return "賃貸マンション";
    if (type === "house") return "賃貸一戸建て";
    return "賃貸その他";
  }
  if (type === "mansion") return "中古マンション";
  if (type === "house") return "中古一戸建て";
  if (type === "land") return "土地";
  if (type === "building") return "一棟売り";
  return "その他";
}

// ─── SUUMO 形式 ─────────────────────────────────────────

const SUUMO_SALE_HEADERS = [
  "物件種目", "所在地_都道府県", "所在地_市区町村", "所在地_町名以降",
  "価格（万円）", "土地面積（㎡）", "建物面積（㎡）", "間取り",
  "築年月", "構造", "階建", "所在階",
  "用途地域", "建ぺい率（%）", "容積率（%）",
  "接道状況_方向", "接道状況_幅員（m）", "私道負担",
  "都市計画", "防火地域",
  "上水道", "下水道", "ガス", "電気",
  "取引態様", "引渡時期",
  "管理費（円/月）", "修繕積立金（円/月）", "管理形態", "総戸数",
  "設備・条件",
  "備考",
];

const SUUMO_RENTAL_HEADERS = [
  "物件種目", "所在地_都道府県", "所在地_市区町村", "所在地_町名以降",
  "賃料（万円）", "管理費・共益費（円）", "敷金", "礼金",
  "土地面積（㎡）", "専有面積（㎡）", "間取り",
  "築年月", "構造", "階建", "所在階",
  "用途地域", "建ぺい率（%）", "容積率（%）",
  "契約期間", "契約形態",
  "上水道", "下水道", "ガス", "電気",
  "更新料", "保証金/敷引",
  "駐車場（円/月）",
  "ペット", "条件・設備",
  "取引態様", "備考",
];

function suumoSaleRow(p: PropertyData): string[] {
  const addr = splitAddress(p.address);
  const priceMan = p.price ? String(Math.round(Number(p.price) / 10000)) : "";
  const notes: string[] = [];
  if (p.flood_text && p.flood_text !== "浸水想定なし") notes.push(`洪水:${p.flood_text}`);
  if (p.tsunami_text && p.tsunami_text !== "浸水想定なし") notes.push(`津波:${p.tsunami_text}`);
  if (p.landslide_text && p.landslide_text !== "区域外") notes.push(`土砂:${p.landslide_text}`);
  if (p.is_incident) notes.push(`告知事項:${p.incident_detail || "あり"}`);
  if (p.special_terms) notes.push(`特約:${p.special_terms}`);

  return [
    portalPropertyType(p.property_type, false),
    addr.pref, addr.city, addr.town,
    priceMan,
    p.land_area || "", p.building_area || "", "",
    "", "", "", "",
    p.zoning || "",
    p.building_coverage_ratio ? String(p.building_coverage_ratio) : "",
    p.floor_area_ratio ? String(p.floor_area_ratio) : "",
    p.road_type || "", p.road_width || "", p.private_road || "",
    p.urban_plan_zone || "", p.fire_zone || "",
    p.water_supply || "", p.sewage || "", p.gas_type || "", p.electricity || "",
    p.transaction_type || "", p.delivery_date || "",
    p.mgmt_fee || "", p.repair_reserve || "", p.mgmt_form || "", p.total_units || "",
    "",
    notes.join(" / "),
  ];
}

function suumoRentalRow(p: PropertyData): string[] {
  const addr = splitAddress(p.address);
  const rentMan = p.rent ? String((Number(p.rent) / 10000).toFixed(1)) : "";
  const notes: string[] = [];
  if (p.flood_text && p.flood_text !== "浸水想定なし") notes.push(`洪水:${p.flood_text}`);
  if (p.is_incident) notes.push(`告知事項:${p.incident_detail || "あり"}`);
  if (p.special_terms) notes.push(`特約:${p.special_terms}`);
  if (p.restoration_terms) notes.push(`原状回復:${p.restoration_terms}`);

  const deposit = p.deposit_months ? `${p.deposit_months}ヶ月` : "";
  const keyMoney = p.key_money_months ? `${p.key_money_months}ヶ月` : "";
  const leaseTerm = p.lease_term_years ? `${p.lease_term_years}年` : "";

  const conditions: string[] = [];
  if (p.pet_allowed && p.pet_allowed !== "不可") conditions.push(`ペット:${p.pet_allowed}`);
  if (p.smoking_allowed) conditions.push(`喫煙:${p.smoking_allowed}`);
  if (p.guarantor_required) conditions.push(`保証人:${p.guarantor_required}`);
  if (p.guarantee_company) conditions.push(`保証会社:${p.guarantee_company}`);
  if (p.fire_insurance) conditions.push(`火災保険:${p.fire_insurance}`);

  return [
    portalPropertyType(p.property_type, true),
    addr.pref, addr.city, addr.town,
    rentMan,
    p.common_area_fee || "",
    deposit, keyMoney,
    p.land_area || "", p.building_area || "", "",
    "", "", "", "",
    p.zoning || "",
    p.building_coverage_ratio ? String(p.building_coverage_ratio) : "",
    p.floor_area_ratio ? String(p.floor_area_ratio) : "",
    leaseTerm, p.lease_type || "",
    p.water_supply || "", p.sewage || "", p.gas_type || "", p.electricity || "",
    p.renewal_fee || "", "",
    p.parking_fee || "",
    p.pet_allowed || "", conditions.join(" / "),
    p.transaction_type || "", notes.join(" / "),
  ];
}

// ─── HOME'S 形式 ─────────────────────────────────────────

const HOMES_SALE_HEADERS = [
  "物件番号", "物件種別", "都道府県", "市区町村", "町名番地",
  "販売価格（万円）", "土地面積（㎡）", "建物面積（㎡）",
  "間取り", "築年", "築月",
  "構造", "階建", "所在階",
  "用途地域", "建ぺい率", "容積率",
  "都市計画区域", "防火指定",
  "接道_方位", "接道_幅員m", "私道面積",
  "水道", "排水", "ガス", "電気",
  "現況", "引渡条件", "引渡時期",
  "取引態様",
  "管理費_月額", "修繕積立金_月額", "管理方式", "総戸数",
  "学区_小学校", "学区_中学校",
  "周辺環境",
  "備考欄",
];

const HOMES_RENTAL_HEADERS = [
  "物件番号", "物件種別", "都道府県", "市区町村", "町名番地",
  "賃料（円）", "共益費（円）", "敷金", "礼金", "保証金",
  "土地面積（㎡）", "専有面積（㎡）",
  "間取り", "築年", "築月",
  "構造", "階建", "所在階",
  "契約期間_年", "契約種別",
  "水道", "排水", "ガス", "電気",
  "更新料", "解約予告（ヶ月前）",
  "駐車場_月額",
  "ペット可否", "楽器可否",
  "保証人", "保証会社",
  "火災保険",
  "用途", "取引態様",
  "学区_小学校", "学区_中学校",
  "備考欄",
];

function homesSaleRow(p: PropertyData): string[] {
  const addr = splitAddress(p.address);
  const priceMan = p.price ? String(Math.round(Number(p.price) / 10000)) : "";
  const notes: string[] = [];
  if (p.flood_text && p.flood_text !== "浸水想定なし") notes.push(`洪水浸水:${p.flood_text}`);
  if (p.tsunami_text && p.tsunami_text !== "浸水想定なし") notes.push(`津波:${p.tsunami_text}`);
  if (p.landslide_text && p.landslide_text !== "区域外") notes.push(`土砂災害:${p.landslide_text}`);
  if (p.is_incident) notes.push(`心理的瑕疵:${p.incident_detail || "あり"}`);
  if (p.special_terms) notes.push(p.special_terms);

  return [
    p.id || "", portalPropertyType(p.property_type, false),
    addr.pref, addr.city, addr.town,
    priceMan, p.land_area || "", p.building_area || "",
    "", "", "",
    "", "", "",
    p.zoning || "",
    p.building_coverage_ratio ? `${p.building_coverage_ratio}%` : "",
    p.floor_area_ratio ? `${p.floor_area_ratio}%` : "",
    p.urban_plan_zone || "", p.fire_zone || "",
    p.road_type || "", p.road_width || "", p.private_road || "",
    p.water_supply || "", p.sewage || "", p.gas_type || "", p.electricity || "",
    "", "", p.delivery_date || "",
    p.transaction_type || "",
    p.mgmt_fee || "", p.repair_reserve || "", p.mgmt_form || "", p.total_units || "",
    p.school_district || "", p.school_district_jr || "",
    "",
    notes.join(" / "),
  ];
}

function homesRentalRow(p: PropertyData): string[] {
  const addr = splitAddress(p.address);
  const notes: string[] = [];
  if (p.flood_text && p.flood_text !== "浸水想定なし") notes.push(`洪水浸水:${p.flood_text}`);
  if (p.is_incident) notes.push(`心理的瑕疵:${p.incident_detail || "あり"}`);
  if (p.special_terms) notes.push(p.special_terms);
  if (p.restoration_terms) notes.push(`原状回復:${p.restoration_terms}`);

  return [
    p.id || "", portalPropertyType(p.property_type, true),
    addr.pref, addr.city, addr.town,
    p.rent || "", p.common_area_fee || "",
    p.deposit_months ? `${p.deposit_months}ヶ月` : "",
    p.key_money_months ? `${p.key_money_months}ヶ月` : "",
    "",
    p.land_area || "", p.building_area || "",
    "", "", "",
    "", "", "",
    p.lease_term_years || "", p.lease_type || "",
    p.water_supply || "", p.sewage || "", p.gas_type || "", p.electricity || "",
    p.renewal_fee || "", p.cancellation_notice || "",
    p.parking_fee || "",
    p.pet_allowed || "", "",
    p.guarantor_required || "", p.guarantee_company || "",
    p.fire_insurance || "",
    p.purpose_of_use || "", p.transaction_type || "",
    p.school_district || "", p.school_district_jr || "",
    notes.join(" / "),
  ];
}

// ─── 公開API ─────────────────────────────────────────────

export type PortalType = "suumo" | "homes";
export type ListingType = "sale" | "rental";

export function detectListingType(p: PropertyData): ListingType {
  // rent が数値として有効な値を持つ場合のみ賃貸と判定
  const rentVal = typeof p.rent === "number" ? p.rent : parseInt(String(p.rent), 10);
  return !isNaN(rentVal) && rentVal > 0 ? "rental" : "sale";
}

export function generatePortalCSV(
  p: PropertyData,
  portal: PortalType,
  listing?: ListingType,
): void {
  const lt = listing ?? detectListingType(p);
  let headers: string[];
  let dataRow: string[];

  if (portal === "suumo") {
    if (lt === "rental") {
      headers = SUUMO_RENTAL_HEADERS;
      dataRow = suumoRentalRow(p);
    } else {
      headers = SUUMO_SALE_HEADERS;
      dataRow = suumoSaleRow(p);
    }
  } else {
    if (lt === "rental") {
      headers = HOMES_RENTAL_HEADERS;
      dataRow = homesRentalRow(p);
    } else {
      headers = HOMES_SALE_HEADERS;
      dataRow = homesSaleRow(p);
    }
  }

  const csvContent = [row(headers), row(dataRow)].join("\n");
  const portalLabel = portal === "suumo" ? "SUUMO" : "HOMES";
  const ltLabel = lt === "rental" ? "賃貸" : "売買";
  const safeAddr = p.address.replace(/[/\\:*?"<>|]/g, "_");
  const date = new Date().toISOString().slice(0, 10);
  const filename = `${portalLabel}_${ltLabel}_${safeAddr}_${date}.csv`;

  download(filename, csvContent);
}

/** 複数物件をまとめて1つのCSVに出力 */
export function generatePortalCSVBulk(
  properties: PropertyData[],
  portal: PortalType,
  listing: ListingType,
): void {
  if (properties.length === 0) return;

  let headers: string[];
  let getRow: (p: PropertyData) => string[];

  if (portal === "suumo") {
    if (listing === "rental") {
      headers = SUUMO_RENTAL_HEADERS;
      getRow = suumoRentalRow;
    } else {
      headers = SUUMO_SALE_HEADERS;
      getRow = suumoSaleRow;
    }
  } else {
    if (listing === "rental") {
      headers = HOMES_RENTAL_HEADERS;
      getRow = homesRentalRow;
    } else {
      headers = HOMES_SALE_HEADERS;
      getRow = homesSaleRow;
    }
  }

  const rows = [row(headers), ...properties.map((p) => row(getRow(p)))];
  const csvContent = rows.join("\n");
  const portalLabel = portal === "suumo" ? "SUUMO" : "HOMES";
  const ltLabel = listing === "rental" ? "賃貸" : "売買";
  const date = new Date().toISOString().slice(0, 10);
  const filename = `${portalLabel}_${ltLabel}_一括_${properties.length}件_${date}.csv`;

  download(filename, csvContent);
}
