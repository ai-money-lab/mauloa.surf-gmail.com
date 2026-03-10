import { latLngToTile } from "./tile-math";

const BASE = "https://www.reinfolib.mlit.go.jp/ex-api/external";

async function fetchTile(
  endpoint: string,
  lat: number,
  lng: number,
  zoom: number,
  apiKey: string
) {
  const { x, y, z } = latLngToTile(lat, lng, zoom);
  const url = `${BASE}/${endpoint}?response_format=geojson&z=${z}&x=${x}&y=${y}`;
  const res = await fetch(url, {
    headers: { "Ocp-Apim-Subscription-Key": apiKey },
  });
  if (!res.ok) return null;
  return res.json();
}

async function fetchTileWithFallback(
  endpoint: string,
  lat: number,
  lng: number,
  zooms: number[],
  apiKey: string
) {
  for (const z of zooms) {
    const result = await fetchTile(endpoint, lat, lng, z, apiKey);
    if (result?.features?.length > 0) return result;
  }
  return null;
}

export async function fetchAllReinfolib(
  lat: number,
  lng: number,
  apiKey: string
) {
  const [zoning, fireZone, urbanPlan, schoolDistrict, landPrice, futurePop] =
    await Promise.allSettled([
      fetchTileWithFallback("XKT002", lat, lng, [14, 13, 12], apiKey),
      fetchTile("XKT014", lat, lng, 14, apiKey),
      fetchTile("XKT001", lat, lng, 11, apiKey),
      fetchTile("XKT004", lat, lng, 12, apiKey),
      fetchTile("XPT002", lat, lng, 13, apiKey),
      fetchTile("XKT013", lat, lng, 11, apiKey),
    ]);

  return {
    zoning: zoning.status === "fulfilled" ? zoning.value : null,
    fireZone: fireZone.status === "fulfilled" ? fireZone.value : null,
    urbanPlan: urbanPlan.status === "fulfilled" ? urbanPlan.value : null,
    schoolDistrict:
      schoolDistrict.status === "fulfilled" ? schoolDistrict.value : null,
    landPrice: landPrice.status === "fulfilled" ? landPrice.value : null,
    futurePop: futurePop.status === "fulfilled" ? futurePop.value : null,
  };
}

export function extractNearestFeature(
  geojson: Record<string, unknown> | null,
  _lat: number,
  _lng: number
): Record<string, unknown> | null {
  const gj = geojson as { features?: Array<{ properties?: Record<string, unknown>; geometry?: { type?: string } }> } | null;
  if (!gj?.features?.length) return null;
  return gj.features[0]?.properties || null;
}
