import { NextRequest, NextResponse } from "next/server";
import { geocode } from "@/lib/api/geocode";
import { fetchAllReinfolib, extractNearestFeature } from "@/lib/api/reinfolib";
import { fetchHazard, floodLevelToText } from "@/lib/api/hazard";

export async function POST(req: NextRequest) {
  const start = Date.now();
  const { address } = await req.json();

  if (!address) {
    return NextResponse.json({ error: "address is required" }, { status: 400 });
  }

  // Step 1: Geocode
  const geo = await geocode(address);
  if (!geo) {
    return NextResponse.json({ error: "住所のジオコーディングに失敗しました" }, { status: 404 });
  }

  const { lat, lng } = geo;
  const apiKey = process.env.REINFOLIB_API_KEY || "";

  // Step 2 & 3: Fetch reinfolib + hazard in parallel
  const [reinfolibData, hazardData] = await Promise.all([
    apiKey ? fetchAllReinfolib(lat, lng, apiKey) : Promise.resolve(null),
    fetchHazard(lat, lng),
  ]);

  // Extract properties from GeoJSON
  const zoningProps = reinfolibData
    ? extractNearestFeature(reinfolibData.zoning as Record<string, unknown> | null, lat, lng)
    : null;
  const fireProps = reinfolibData
    ? extractNearestFeature(reinfolibData.fireZone as Record<string, unknown> | null, lat, lng)
    : null;
  const urbanProps = reinfolibData
    ? extractNearestFeature(reinfolibData.urbanPlan as Record<string, unknown> | null, lat, lng)
    : null;
  const schoolProps = reinfolibData
    ? extractNearestFeature(reinfolibData.schoolDistrict as Record<string, unknown> | null, lat, lng)
    : null;
  const landPriceProps = reinfolibData
    ? extractNearestFeature(reinfolibData.landPrice as Record<string, unknown> | null, lat, lng)
    : null;
  const futurePopProps = reinfolibData
    ? extractNearestFeature(reinfolibData.futurePop as Record<string, unknown> | null, lat, lng)
    : null;

  // Build sediment risk
  let sedimentRisk = 0;
  if (hazardData) {
    if (hazardData.dosekiryukeikaikuiki) sedimentRisk += 1;
    if (hazardData.kyukeishakeikaikuiki) sedimentRisk += 1;
    if (hazardData.jisuberikeikaikuiki) sedimentRisk += 1;
  }

  const result = {
    lat,
    lng,
    // Zoning
    zoning: zoningProps?.["用途地域"] as string || zoningProps?.["youto"] as string || null,
    building_coverage_ratio: zoningProps?.["建ぺい率"] as number || zoningProps?.["kenpei"] as number || null,
    floor_area_ratio: zoningProps?.["容積率"] as number || zoningProps?.["youseki"] as number || null,
    // Fire zone
    fire_zone: fireProps?.["防火地域"] as string || fireProps?.["bouka"] as string || null,
    height_district: zoningProps?.["高度地区"] as string || null,
    // Urban plan
    urban_plan_zone: urbanProps?.["区域区分"] as string || null,
    // Hazard
    flood_level: hazardData?.flood_l2 ?? 0,
    flood_text: hazardData ? floodLevelToText(hazardData.flood_l2) : null,
    flood_river: null,
    tsunami_level: hazardData?.tsunami_newlegend ?? 0,
    tsunami_text: hazardData ? floodLevelToText(hazardData.tsunami_newlegend) : null,
    hightide_level: hazardData?.hightide ?? 0,
    hightide_text: hazardData ? floodLevelToText(hazardData.hightide) : null,
    landslide_text: sedimentRisk > 0 ? "警戒区域内" : "区域外",
    sediment_risk: sedimentRisk,
    // School
    school_district: schoolProps?.["小学校名"] as string || schoolProps?.["A27_005"] as string || null,
    school_district_jr: schoolProps?.["中学校名"] as string || null,
    // Land price
    land_price: landPriceProps?.["価格"] as number || landPriceProps?.["L01_006"] as number || null,
    land_price_year: landPriceProps?.["年度"] as number || null,
    land_price_point: landPriceProps?.["所在"] as string || null,
    // Future pop
    future_pop: futurePopProps?.["現在人口"] as number || null,
    future_pop_2050: futurePopProps?.["2050年人口"] as number || null,
    future_pop_change: futurePopProps?.["変化率"] as number || null,
    // Timing
    elapsed_ms: Date.now() - start,
  };

  return NextResponse.json(result);
}
