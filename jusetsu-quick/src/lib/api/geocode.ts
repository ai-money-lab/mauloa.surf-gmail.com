/**
 * 国土地理院ジオコーディング
 * 住所 → {lat, lng}
 * 認証不要・完全無料
 */
export async function geocode(
  address: string
): Promise<{ lat: number; lng: number } | null> {
  const url = `https://msearch.gsi.go.jp/address-search/AddressSearch?q=${encodeURIComponent(address)}`;
  const res = await fetch(url);
  const data = await res.json();
  if (!data || data.length === 0) return null;
  const [lng, lat] = data[0].geometry.coordinates;
  return { lat, lng };
}
