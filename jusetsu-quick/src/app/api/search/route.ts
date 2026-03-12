import { NextRequest, NextResponse } from "next/server";
import { geocode } from "@/lib/api/geocode";
import { fetchAllReinfolib, extractNearestFeature } from "@/lib/api/reinfolib";
import {
  fetchHazard,
  floodLevelToText,
  tsunamiLevelToText,
  hightideLevelToText,
  parseSedimentRisk,
} from "@/lib/api/hazard";

export const runtime = "edge";

// ── helpers ────────────────────────────────────────────────

/** Return first non-nullish value from props for given keys */
function pick(
  props: Record<string, unknown> | null,
  ...keys: string[]
): unknown | null {
  if (!props) return null;
  for (const k of keys) {
    if (props[k] !== undefined && props[k] !== null) return props[k];
  }
  return null;
}

/** Search all props keys for partial matches (case-insensitive) */
function pickByPartial(
  props: Record<string, unknown> | null,
  ...needles: string[]
): unknown | null {
  if (!props) return null;
  for (const [k, v] of Object.entries(props)) {
    if (v === null || v === undefined) continue;
    const kl = k.toLowerCase();
    for (const needle of needles) {
      if (kl.includes(needle.toLowerCase())) return v;
    }
  }
  return null;
}

/** Pick a numeric value: first tries exact keys, then partial, returns number|null */
function pickNumber(
  props: Record<string, unknown> | null,
  exactKeys: string[],
  partialKeys: string[]
): number | null {
  const raw = pick(props, ...exactKeys) ?? pickByPartial(props, ...partialKeys);
  if (raw === null || raw === undefined) return null;
  const n = typeof raw === "number" ? raw : Number(raw);
  if (isNaN(n)) return null;
  return n;
}

/** Pick a string value: first tries exact keys, then partial */
function pickString(
  props: Record<string, unknown> | null,
  exactKeys: string[],
  partialKeys: string[] = []
): string | null {
  const raw = pick(props, ...exactKeys) ?? (partialKeys.length ? pickByPartial(props, ...partialKeys) : null);
  if (raw === null || raw === undefined) return null;
  return String(raw);
}

/**
 * Normalize a ratio value: if decimal (<=1), multiply by 100.
 */
function normalizeRatio(value: number | null): number | null {
  if (value === null) return null;
  if (value > 0 && value <= 1) return Math.round(value * 100);
  return value;
}

// ── Zoning → BCR/FAR lookup table (法定上限) ────────────────
// 用途地域が取れたが建ぺい率・容積率がAPIから取れない場合のフォールバック
const ZONING_DEFAULTS: Record<string, { bcr: number; far: string }> = {
  "第一種低層住居専用地域": { bcr: 50, far: "50〜200" },
  "第二種低層住居専用地域": { bcr: 50, far: "50〜200" },
  "第一種中高層住居専用地域": { bcr: 60, far: "100〜500" },
  "第二種中高層住居専用地域": { bcr: 60, far: "100〜500" },
  "第一種住居地域": { bcr: 60, far: "100〜500" },
  "第二種住居地域": { bcr: 60, far: "100〜500" },
  "準住居地域": { bcr: 60, far: "100〜500" },
  "田園住居地域": { bcr: 50, far: "50〜200" },
  "近隣商業地域": { bcr: 80, far: "100〜500" },
  "商業地域": { bcr: 80, far: "200〜1300" },
  "準工業地域": { bcr: 60, far: "100〜500" },
  "工業地域": { bcr: 60, far: "100〜400" },
  "工業専用地域": { bcr: 60, far: "100〜400" },
};

// ── Main handler ────────────────────────────────────────────

export async function POST(req: NextRequest) {
  const start = Date.now();

  let body: { address?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { address } = body;
  if (!address || typeof address !== "string") {
    return NextResponse.json({ error: "address is required" }, { status: 400 });
  }

  // Step 1: Geocode
  let geo: { lat: number; lng: number } | null;
  try {
    geo = await geocode(address);
  } catch {
    return NextResponse.json({ error: "ジオコーディングサービスに接続できません" }, { status: 502 });
  }
  if (!geo) {
    return NextResponse.json({ error: "住所のジオコーディングに失敗しました。住所を確認してください。" }, { status: 404 });
  }

  const { lat, lng } = geo;
  const apiKey = process.env.REINFOLIB_API_KEY;
  if (!apiKey) {
    console.error("REINFOLIB_API_KEY is not configured");
  }

  // Step 2 & 3: Fetch reinfolib + hazard in parallel
  let reinfolibData: Awaited<ReturnType<typeof fetchAllReinfolib>> | null = null;
  let hazardData: Awaited<ReturnType<typeof fetchHazard>> | null = null;
  const apiErrors: Record<string, string> = {};

  const [reinfolibResult, hazardResult] = await Promise.allSettled([
    apiKey ? fetchAllReinfolib(lat, lng, apiKey) : Promise.resolve(null),
    fetchHazard(lat, lng),
  ]);

  if (reinfolibResult.status === "fulfilled") {
    reinfolibData = reinfolibResult.value;
  } else {
    apiErrors.reinfolib = reinfolibResult.reason?.message ?? "Unknown error";
  }

  if (hazardResult.status === "fulfilled") {
    hazardData = hazardResult.value;
  } else {
    apiErrors.hazard = hazardResult.reason?.message ?? "Unknown error";
  }

  // Extract nearest features from GeoJSON
  const zoningProps = reinfolibData
    ? extractNearestFeature(reinfolibData.zoning as Record<string, unknown> | null, lat, lng, 500)
    : null;
  const fireProps = reinfolibData
    ? extractNearestFeature(reinfolibData.fireZone as Record<string, unknown> | null, lat, lng, 500)
    : null;
  const urbanProps = reinfolibData
    ? extractNearestFeature(reinfolibData.urbanPlan as Record<string, unknown> | null, lat, lng, 2000)
    : null;
  const schoolProps = reinfolibData
    ? extractNearestFeature(reinfolibData.schoolDistrict as Record<string, unknown> | null, lat, lng, 3000)
    : null;
  const schoolJrProps = reinfolibData
    ? extractNearestFeature(reinfolibData.schoolDistrictJr as Record<string, unknown> | null, lat, lng, 3000)
    : null;
  const landPriceProps = reinfolibData
    ? extractNearestFeature(reinfolibData.landPrice as Record<string, unknown> | null, lat, lng, 5000)
    : null;
  const futurePopProps = reinfolibData
    ? extractNearestFeature(reinfolibData.futurePop as Record<string, unknown> | null, lat, lng, 5000)
    : null;

  // ── Extract values ──

  // Zoning name (用途地域名)
  // 国土数値情報 A29: A29_005=用途地域名, Reinfolib may use _ja suffix or different names
  const zoning = pickString(zoningProps,
    ["A29_005", "A29_005_ja", "A29_004_ja", "use_area_ja", "用途地域", "youto", "A29_004", "A09_004"],
    ["用途", "zoning", "use_area"]
  );

  // Building Coverage Ratio (建蔽率): A29_006, or scan for "coverage/kenpei/建蔽"
  let bcr = normalizeRatio(pickNumber(zoningProps,
    ["A29_006", "A29_006_ja", "建ぺい率", "建蔽率", "kenpei", "A09_006"],
    ["building_coverage", "kenpei", "建ぺい", "建蔽", "coverage"]
  ));
  // Also check fireProps
  if (bcr === null) {
    bcr = normalizeRatio(pickNumber(fireProps,
      ["建ぺい率", "建蔽率", "kenpei", "building_coverage"],
      ["kenpei", "建蔽", "coverage"]
    ));
  }

  // Floor Area Ratio (容積率): A29_007, or scan for "floor_area/youseki/容積"
  let far = normalizeRatio(pickNumber(zoningProps,
    ["A29_007", "A29_007_ja", "容積率", "youseki", "A09_007"],
    ["floor_area", "youseki", "容積"]
  ));
  if (far === null) {
    far = normalizeRatio(pickNumber(fireProps,
      ["容積率", "youseki", "floor_area"],
      ["youseki", "容積"]
    ));
  }

  // Fallback: derive BCR/FAR hint from zoning name
  let bcrFarSource: string | null = null;
  if (zoning && (bcr === null || far === null)) {
    const defaults = ZONING_DEFAULTS[zoning as string];
    if (defaults) {
      if (bcr === null) bcr = defaults.bcr;
      if (far === null) far = null; // Don't guess FAR (it's a range)
      bcrFarSource = "用途地域から推定";
    }
  }

  // Fire zone
  const fireZone = pickString(fireProps,
    ["fire_prevention_ja", "防火地域", "防火・準防火地域", "A09_005", "bouka", "kubun_id"],
    ["fire", "防火", "bouka"]
  );

  // Height district
  const heightDistrict =
    pickString(zoningProps, ["高度地区", "height_district", "koudo"]) ??
    pickString(fireProps, ["高度地区", "height_district"]) ??
    pickString(urbanProps, ["高度地区", "height_district"]);

  // Land price
  const landPrice = pickNumber(landPriceProps,
    ["L01_006", "current_price", "価格", "標準価格"],
    ["price", "価格", "kakaku"]
  );

  // School districts
  const schoolDistrict = pickString(schoolProps,
    ["A27_005", "A27_005_ja", "小学校名", "school_name"],
    ["小学校", "school"]
  );
  const schoolDistrictJr =
    pickString(schoolJrProps, ["A32_005", "A32_005_ja", "中学校名", "school_name"]) ??
    pickString(schoolProps, ["A27_006", "中学校名"]);

  // Future population
  const futurePop = pickNumber(futurePopProps, ["PTN_2020", "現在人口", "population"], []);
  const futurePop2050 = pickNumber(futurePopProps, ["PTN_2050", "2050年人口"], []);
  const futurePopChange = (() => {
    if (futurePop && futurePop2050 && futurePop > 0) {
      return Math.round((futurePop2050 / futurePop) * 100 - 100);
    }
    return pickNumber(futurePopProps, ["変化率"], []);
  })();

  // Hazard
  const sediment = parseSedimentRisk(hazardData);

  const result = {
    lat,
    lng,
    zoning,
    building_coverage_ratio: bcr,
    floor_area_ratio: far,
    bcr_far_source: bcrFarSource,
    fire_zone: fireZone,
    height_district: heightDistrict,
    urban_plan_zone: pickString(urbanProps, ["区域区分", "urban_plan"], ["区域"]),
    // Hazard - default to "想定区域外" when API returns null/0
    flood_level: hazardData?.flood_l2 ?? 0,
    flood_text: hazardData ? floodLevelToText(hazardData.flood_l2) : "想定区域外",
    flood_river: null as string | null,
    tsunami_level: hazardData?.tsunami_newlegend ?? 0,
    tsunami_text: hazardData ? tsunamiLevelToText(hazardData.tsunami_newlegend) : "想定区域外",
    hightide_level: hazardData?.hightide ?? 0,
    hightide_text: hazardData ? hightideLevelToText(hazardData.hightide) : "想定区域外",
    landslide_text: sediment.text,
    sediment_risk: sediment.count,
    sediment_detail: {
      debris_flow: sediment.debrisFlow,
      steep_slope: sediment.steepSlope,
      landslide: sediment.landslide,
    },
    school_district: schoolDistrict,
    school_district_jr: schoolDistrictJr,
    land_price: landPrice,
    land_price_year: pickNumber(landPriceProps, ["L01_003", "survey_year", "年度", "調査年"], []),
    land_price_point: pickString(landPriceProps, ["L01_025", "address", "所在", "所在及び地番"]),
    future_pop: futurePop,
    future_pop_2050: futurePop2050,
    future_pop_change: futurePopChange,
    // Diagnostics (will be stripped before DB save)
    api_errors: Object.keys(apiErrors).length > 0 ? apiErrors : undefined,
    data_sources: {
      reinfolib: reinfolibData !== null,
      hazard: hazardData !== null,
    },
    _debug_fields: {
      zoning: zoningProps ? Object.keys(zoningProps) : null,
      fire: fireProps ? Object.keys(fireProps) : null,
      landPrice: landPriceProps ? Object.keys(landPriceProps) : null,
    },
    _debug_raw_zoning: zoningProps,
    elapsed_ms: Date.now() - start,
  };

  return NextResponse.json(result);
}
