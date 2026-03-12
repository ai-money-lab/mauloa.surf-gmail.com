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

export interface SedimentRiskDetail {
  count: number;
  debrisFlow: boolean;   // 土石流 (dosekiryukeikaikuiki)
  steepSlope: boolean;   // 急傾斜地 (kyukeishakeikaikuiki)
  landslide: boolean;    // 地すべり (jisuberikeikaikuiki)
  text: string;
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

export function tsunamiLevelToText(level: number): string {
  const map: Record<number, string> = {
    0: "想定区域外",
    1: "0.3m未満",
    2: "0.3〜1.0m未満",
    3: "1.0〜2.0m未満",
    4: "2.0〜3.0m未満",
    5: "3.0〜5.0m未満",
    6: "5.0〜10.0m未満",
    7: "10.0〜20.0m未満",
    8: "20.0m以上",
  };
  return map[level] || "不明";
}

export function hightideLevelToText(level: number): string {
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

export function parseSedimentRisk(hazard: HazardInfo | null): SedimentRiskDetail {
  if (!hazard) {
    return { count: 0, debrisFlow: false, steepSlope: false, landslide: false, text: "区域外" };
  }

  const debrisFlow = !!hazard.dosekiryukeikaikuiki;
  const steepSlope = !!hazard.kyukeishakeikaikuiki;
  const landslide = !!hazard.jisuberikeikaikuiki;
  const count = (debrisFlow ? 1 : 0) + (steepSlope ? 1 : 0) + (landslide ? 1 : 0);

  if (count === 0) {
    return { count, debrisFlow, steepSlope, landslide, text: "区域外" };
  }

  const types: string[] = [];
  if (debrisFlow) types.push("土石流警戒区域");
  if (steepSlope) types.push("急傾斜地警戒区域");
  if (landslide) types.push("地すべり警戒区域");

  return { count, debrisFlow, steepSlope, landslide, text: types.join("・") };
}
