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
  const landPriceProps = reinfolibData
    ? extractNearestFeature(reinfolibData.landPrice as Record<string, unknown> | null, lat, lng, 5000)
    : null;
  const futurePopProps = reinfolibData
    ? extractNearestFeature(reinfolibData.futurePop as Record<string, unknown> | null, lat, lng, 5000)
    : null;

  // Build sediment risk with detail
  const sediment = parseSedimentRisk(hazardData);

  // Extract zoning fields trying multiple possible field names
  const zoningValue = tryFields(zoningProps, "用途地域", "youto", "A29_004", "A09_004");
  const bcrRaw = tryFields(zoningProps, "建ぺい率", "kenpei", "A29_005", "A09_006");
  const farRaw = tryFields(zoningProps, "容積率", "youseki", "A29_006", "A09_007");
  const fireZoneValue = tryFields(fireProps, "防火地域", "A09_005", "bouka");

  const result = {
    lat,
    lng,
    // Zoning
    zoning: (zoningValue as string) ?? null,
    building_coverage_ratio: normalizeRatio(bcrRaw),
    floor_area_ratio: normalizeRatio(farRaw),
    // Fire zone
    fire_zone: (fireZoneValue as string) ?? null,
    height_district: (tryFields(zoningProps, "高度地区") as string) ?? null,
    // Urban plan
    urban_plan_zone: (tryFields(urbanProps, "区域区分") as string) ?? null,
    // Hazard
    flood_level: hazardData?.flood_l2 ?? null,
    flood_text: hazardData ? floodLevelToText(hazardData.flood_l2) : null,
    flood_river: null,
    tsunami_level: hazardData?.tsunami_newlegend ?? null,
    tsunami_text: hazardData ? tsunamiLevelToText(hazardData.tsunami_newlegend) : null,
    hightide_level: hazardData?.hightide ?? null,
    hightide_text: hazardData ? hightideLevelToText(hazardData.hightide) : null,
    landslide_text: sediment.text,
    sediment_risk: sediment.count,
    sediment_detail: {
      debris_flow: sediment.debrisFlow,
      steep_slope: sediment.steepSlope,
      landslide: sediment.landslide,
    },
    // School
    school_district: (tryFields(schoolProps, "小学校名", "A27_005") as string) ?? null,
    school_district_jr: (tryFields(schoolProps, "中学校名", "A27_006") as string) ?? null,
    // Land price
    land_price: (tryFields(landPriceProps, "価格", "L01_006") as number) ?? null,
    land_price_year: (tryFields(landPriceProps, "年度", "L01_003") as number) ?? null,
    land_price_point: (tryFields(landPriceProps, "所在", "L01_025") as string) ?? null,
    // Future pop
    future_pop: (tryFields(futurePopProps, "現在人口") as number) ?? null,
    future_pop_2050: (tryFields(futurePopProps, "2050年人口") as number) ?? null,
    future_pop_change: (tryFields(futurePopProps, "変化率") as number) ?? null,
    // Diagnostics
    api_errors: Object.keys(apiErrors).length > 0 ? apiErrors : undefined,
    data_sources: {
      reinfolib: reinfolibData !== null,
      hazard: hazardData !== null,
    },
    // Timing
    elapsed_ms: Date.now() - start,
  };

  return NextResponse.json(result);
}
