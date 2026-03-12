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
  const fallbackZooms = [15, 14, 13, 12];

  const [zoning, fireZone, urbanPlan, schoolDistrict, landPrice, futurePop] =
    await Promise.allSettled([
      fetchTileWithFallback("XKT002", lat, lng, fallbackZooms, apiKey),
      fetchTileWithFallback("XKT014", lat, lng, fallbackZooms, apiKey),
      fetchTileWithFallback("XKT001", lat, lng, [15, 14, 13, 12, 11], apiKey),
      fetchTileWithFallback("XKT004", lat, lng, fallbackZooms, apiKey),
      fetchTileWithFallback("XPT002", lat, lng, fallbackZooms, apiKey),
      fetchTileWithFallback("XKT013", lat, lng, [15, 14, 13, 12, 11], apiKey),
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

function haversineDistance(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371000; // meters
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLng / 2) * Math.sin(dLng / 2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function getCentroid(feature: { geometry?: { type?: string; coordinates?: unknown } }): [number, number] | null {
  const geom = feature?.geometry;
  if (!geom) return null;
  if (geom.type === "Point") {
    const coords = geom.coordinates as [number, number];
    return [coords[1], coords[0]]; // [lat, lng]
  }
  // For Polygon/MultiPolygon, calculate centroid from first ring
  const coords = geom.type === "Polygon"
    ? (geom.coordinates as number[][][])[0]
    : geom.type === "MultiPolygon"
      ? (geom.coordinates as number[][][][])[0][0]
      : null;
  if (!coords?.length) return null;
  const sum = coords.reduce(
    (acc: [number, number], c: number[]) => [acc[0] + c[1], acc[1] + c[0]],
    [0, 0]
  );
  return [sum[0] / coords.length, sum[1] / coords.length];
}

export function extractNearestFeature(
  geojson: Record<string, unknown> | null,
  lat: number,
  lng: number,
  maxDistanceM = 1000
): Record<string, unknown> | null {
  const gj = geojson as {
    features?: Array<{ properties?: Record<string, unknown>; geometry?: { type?: string; coordinates?: unknown } }>;
  } | null;
  if (!gj?.features?.length) return null;

  let nearest: (typeof gj.features)[number] | null = null;
  let minDist = Infinity;

  for (const f of gj.features) {
    const centroid = getCentroid(f);
    if (!centroid) continue;
    const dist = haversineDistance(lat, lng, centroid[0], centroid[1]);
    if (dist < minDist) {
      minDist = dist;
      nearest = f;
    }
  }

  if (minDist > maxDistanceM) return null;
  return nearest?.properties ?? null;
}
