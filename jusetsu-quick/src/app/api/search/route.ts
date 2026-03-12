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

/** Try multiple possible field names, return first non-nullish value */
function tryFields(
  props: Record<string, unknown> | null,
  ...keys: string[]
): unknown | null {
  if (!props) return null;
  for (const k of keys) {
    if (props[k] !== undefined && props[k] !== null) return props[k];
  }
  return null;
}

/**
 * Normalize a ratio value: if it looks like a decimal (<=1), multiply by 100.
 * Returns a percentage number or null.
 */
function normalizeRatio(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  const n = typeof value === "number" ? value : Number(value);
  if (isNaN(n)) return null;
  // If value is a decimal like 0.6, convert to 60
  if (n > 0 && n <= 1) return Math.round(n * 100);
  return n;
}

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

  // Step 2 & 3: Fetch reinfolib + hazard in parallel (graceful degradation)
  let reinfolibData: Awaited<ReturnType<typeof fetchAllReinfolib>> | null = null;
  let hazardData: Awaited<ReturnType<typeof fetchHazard>> | null = null;

  // Track API errors for diagnostics
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

  // Extract properties from GeoJSON with appropriate max distances
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

  // Build sediment risk with detail
  const sediment = parseSedimentRisk(hazardData);

  // Extract zoning fields - try all possible reinfolib field names, then smart-match
  const zoningValue = tryFields(zoningProps, "use_area_ja", "用途地域", "youto", "A29_004", "A09_004");

  // For BCR/FAR, try known field names first, then scan all properties
  let bcrRaw = tryFields(zoningProps, "u_building_coverage_ratio_ja", "建ぺい率", "建蔽率", "kenpei", "A29_005", "A09_006");
  let farRaw = tryFields(zoningProps, "u_floor_area_ratio_ja", "容積率", "youseki", "A29_006", "A09_007");

  // Smart scan: if BCR/FAR still null, search zoningProps keys for partial matches
  if (zoningProps && (bcrRaw === null || farRaw === null)) {
    for (const [k, v] of Object.entries(zoningProps)) {
      if (v === null || v === undefined) continue;
      const kl = k.toLowerCase();
      if (bcrRaw === null && (kl.includes("building_coverage") || kl.includes("kenpei") || kl.includes("建ぺい") || kl.includes("建蔽"))) {
        bcrRaw = v;
      }
      if (farRaw === null && (kl.includes("floor_area") || kl.includes("youseki") || kl.includes("容積"))) {
        farRaw = v;
      }
    }
  }

  // Also try from fireProps (some datasets bundle ratios there)
  if (bcrRaw === null) bcrRaw = tryFields(fireProps, "建ぺい率", "建蔽率", "kenpei", "building_coverage");
  if (farRaw === null) farRaw = tryFields(fireProps, "容積率", "youseki", "floor_area");

  // Height district: try multiple sources
  const heightDistrict = tryFields(zoningProps, "高度地区", "height_district", "koudo")
    ?? tryFields(fireProps, "高度地区", "height_district")
    ?? tryFields(urbanProps, "高度地区", "height_district");

  // Fire zone: also smart-match
  let fireZoneValue = tryFields(fireProps, "fire_prevention_ja", "防火地域", "防火・準防火地域", "A09_005", "bouka", "kubun_id");
  if (fireProps && fireZoneValue === null) {
    for (const [k, v] of Object.entries(fireProps)) {
      if (v === null || v === undefined) continue;
      const kl = k.toLowerCase();
      if (kl.includes("fire") || kl.includes("防火") || kl.includes("bouka")) {
        fireZoneValue = v;
        break;
      }
    }
  }

  // Land price: also try smart match
  let landPriceValue = tryFields(landPriceProps, "L01_006", "current_price", "価格", "標準価格") as number | null;
  if (landPriceProps && landPriceValue === null) {
    for (const [k, v] of Object.entries(landPriceProps)) {
      if (v === null || v === undefined) continue;
      const kl = k.toLowerCase();
      if (kl.includes("price") || kl.includes("価格") || kl.includes("kakaku")) {
        const n = Number(v);
        if (!isNaN(n) && n > 0) { landPriceValue = n; break; }
      }
    }
  }

  const result = {
    lat,
    lng,
    // Zoning
    zoning: (zoningValue as string) ?? null,
    building_coverage_ratio: normalizeRatio(bcrRaw),
    floor_area_ratio: normalizeRatio(farRaw),
    // Fire zone
    fire_zone: (fireZoneValue as string) ?? null,
    height_district: (heightDistrict as string) ?? null,
    // Urban plan
    urban_plan_zone: (tryFields(urbanProps, "区域区分") as string) ?? null,
    // Hazard - default to "想定区域外" when API unavailable (not "null")
    flood_level: hazardData?.flood_l2 ?? 0,
    flood_text: hazardData ? floodLevelToText(hazardData.flood_l2) : "想定区域外",
    flood_river: null,
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
    // School (XKT004 returns A27_005/school_name fields)
    school_district: (tryFields(schoolProps, "A27_005", "小学校名", "school_name") as string) ?? null,
    school_district_jr: (tryFields(schoolJrProps, "A32_005", "中学校名", "school_name") ??
      tryFields(schoolProps, "A27_006", "中学校名")) as string ?? null,
    // Land price (XPT002 - 地価公示ポイントAPI)
    land_price: landPriceValue,
    land_price_year: (tryFields(landPriceProps, "L01_003", "survey_year", "年度", "調査年") as number) ?? null,
    land_price_point: (tryFields(landPriceProps, "L01_025", "address", "所在", "所在及び地番") as string) ?? null,
    // Future pop (XKT013 - 将来推計人口500mメッシュ)
    future_pop: (tryFields(futurePopProps, "PTN_2020", "現在人口", "population") as number) ?? null,
    future_pop_2050: (tryFields(futurePopProps, "PTN_2050", "2050年人口") as number) ?? null,
    future_pop_change: (() => {
      const pop2020 = tryFields(futurePopProps, "PTN_2020", "現在人口") as number | null;
      const pop2050 = tryFields(futurePopProps, "PTN_2050", "2050年人口") as number | null;
      if (pop2020 && pop2050 && pop2020 > 0) return Math.round((pop2050 / pop2020) * 100 - 100);
      return (tryFields(futurePopProps, "変化率") as number) ?? null;
    })(),
    // Diagnostics
    api_errors: Object.keys(apiErrors).length > 0 ? apiErrors : undefined,
    data_sources: {
      reinfolib: reinfolibData !== null,
      hazard: hazardData !== null,
    },
    // Debug: raw property keys from each API (helps diagnose field name mismatches)
    _debug_fields: {
      zoning: zoningProps ? Object.keys(zoningProps) : null,
      fire: fireProps ? Object.keys(fireProps) : null,
      urban: urbanProps ? Object.keys(urbanProps) : null,
      landPrice: landPriceProps ? Object.keys(landPriceProps) : null,
      futurePop: futurePopProps ? Object.keys(futurePopProps) : null,
      school: schoolProps ? Object.keys(schoolProps) : null,
    },
    _debug_raw: {
      zoning: zoningProps,
      fire: fireProps,
      landPrice: landPriceProps,
    },
    // Timing
    elapsed_ms: Date.now() - start,
  };

  return NextResponse.json(result);
}
