export interface HazardInfo {
  flood_l2: number;
  hightide: number;
  tsunami_newlegend: number;
  dosekiryukeikaikuiki: boolean;
  kyukeishakeikaikuiki: boolean;
  jisuberikeikaikuiki: boolean;
  kaokutoukai_hanran: boolean;
  kaokutoukai_kagan: boolean;
}

export async function fetchHazard(
  lat: number,
  lng: number
): Promise<HazardInfo | null> {
  try {
    const res = await fetch(
      `https://hazards.utsuken.net/api/v1/outline?lat=${lat}&lng=${lng}`
    );
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export function floodLevelToText(level: number): string {
  const map: Record<number, string> = {
    0: "想定区域外",
    1: "0.0〜0.3m未満",
    2: "0.3〜0.5m未満",
    3: "0.5〜1.0m未満",
    4: "1.0〜2.0m未満",
    5: "2.0〜3.0m未満",
    6: "3.0〜5.0m未満",
    7: "5.0〜10.0m未満",
    8: "10.0m以上",
  };
  return map[level] || "不明";
}
