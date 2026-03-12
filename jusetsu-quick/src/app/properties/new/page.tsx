"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Search, MapPin, Shield, Droplets, Building2,
  ChevronLeft, Download, Save,
  Home, LandPlot, Warehouse,
  CheckCircle2, ArrowRight, Database,
  DollarSign, Route, Plug, FileText,
  ClipboardCheck, TriangleAlert, Scale, Check, AlertTriangle,
  Info,
} from "lucide-react";
import Header from "@/components/Header";
import StepNav from "@/components/StepNav";
import Section from "@/components/ui/Section";
import Btn from "@/components/ui/Btn";
import AutoRow from "@/components/ui/AutoRow";
import Field from "@/components/ui/Field";
import LoadingLine from "@/components/ui/LoadingLine";
import Tag from "@/components/ui/Tag";
import type { PropertyData, SearchResult } from "@/lib/types";

const PROPERTY_TYPES = [
  { v: "mansion", label: "区分マンション", Icon: Building2 },
  { v: "land", label: "土地", Icon: LandPlot },
  { v: "house", label: "一戸建て", Icon: Home },
  { v: "building", label: "一棟", Icon: Warehouse },
];

const LOCAL_STORAGE_KEY = "jusetsu_new_property_draft";

function computeCompletion(
  formData: Partial<PropertyData>,
  apiData: SearchResult | null,
  pType: string,
  incident: boolean
): { filled: number; total: number; percent: number } {
  const fields: boolean[] = [
    // API fields
    !!apiData?.zoning,
    !!apiData?.building_coverage_ratio,
    !!apiData?.floor_area_ratio,
    !!apiData?.fire_zone,
    !!apiData?.flood_text,
    !!apiData?.tsunami_text,
    !!apiData?.hightide_text,
    !!apiData?.landslide_text,
    !!apiData?.land_price,
    // Manual fields
    !!formData.water_supply,
    !!formData.sewage,
    !!formData.gas_type,
    !!formData.electricity,
    !!formData.road_type,
    !!formData.road_width,
    !!formData.owner_name,
    !!formData.land_area,
    !!formData.mortgage,
    !!formData.price,
    !!formData.transaction_type,
    !!formData.asbestos,
    !!formData.earthquake_resistance,
  ];
  if (pType === "mansion") {
    fields.push(!!formData.mgmt_fee, !!formData.repair_reserve, !!formData.mgmt_form);
  }
  if (incident) {
    fields.push(!!formData.incident_detail);
  }
  const filled = fields.filter(Boolean).length;
  const total = fields.length;
  return { filled, total, percent: total > 0 ? Math.round((filled / total) * 100) : 0 };
}

function isValidNumber(val: string | undefined): boolean {
  if (!val || val === "") return true; // empty is ok
  return !isNaN(Number(val)) && val.trim() !== "";
}

function ProgressBar({ percent }: { percent: number }) {
  const color = percent >= 80 ? "#166534" : percent >= 50 ? "#854D0E" : "#B91C1C";
  const bg = percent >= 80 ? "#DCFCE7" : percent >= 50 ? "#FEF9C3" : "#FEE2E2";
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color }}>入力進捗</span>
        <span style={{ fontSize: 13, fontWeight: 800, color }}>{percent}%</span>
      </div>
      <div style={{ background: "#E2E8F0", borderRadius: 6, height: 8, overflow: "hidden" }}>
        <div style={{ height: "100%", background: color, borderRadius: 6, width: `${percent}%`, transition: "width 0.4s" }} />
      </div>
    </div>
  );
}

function DataSourceBadge({ source, official }: { source: string; official: boolean }) {
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      fontSize: 10, fontWeight: 600, padding: "2px 6px", borderRadius: 4,
      background: official ? "#DBEAFE" : "#F1F5F9",
      color: official ? "#1D4ED8" : "#64748B",
      border: `1px solid ${official ? "#93C5FD" : "#CBD5E1"}`,
    }}>
      {official ? <Shield size={10} /> : <Info size={10} />}
      {source}
    </div>
  );
}

function NumericValidation({ value }: { value: string | undefined }) {
  if (!value || value === "" || isValidNumber(value)) return null;
  return (
    <div style={{ fontSize: 11, color: "#B91C1C", fontWeight: 600, marginTop: 4 }}>
      数値を入力してください
    </div>
  );
}

export default function NewPropertyPage() {
  const [step, setStep] = useState(1);
  const [address, setAddress] = useState("");
  const [pType, setPType] = useState("mansion");
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState(0);
  const [incident, setIncident] = useState(false);
  const [apiData, setApiData] = useState<SearchResult | null>(null);
  const [formData, setFormData] = useState<Partial<PropertyData>>({});

  const go = (s: number) => {
    setStep(s);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Auto-save to localStorage
  const saveToLocalStorage = useCallback(() => {
    try {
      const draft = { address, pType, incident, formData, apiData, step };
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(draft));
    } catch { /* ignore */ }
  }, [address, pType, incident, formData, apiData, step]);

  const autoSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const updateForm = (key: string, val: string) => {
    setFormData((prev) => ({ ...prev, [key]: val }));
  };

  // Debounced auto-save
  useEffect(() => {
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    autoSaveTimer.current = setTimeout(saveToLocalStorage, 500);
    return () => { if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current); };
  }, [saveToLocalStorage]);

  // Restore from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (saved) {
        const draft = JSON.parse(saved);
        if (draft.address) setAddress(draft.address);
        if (draft.pType) setPType(draft.pType);
        if (draft.incident) setIncident(draft.incident);
        if (draft.formData) setFormData(draft.formData);
        if (draft.apiData) setApiData(draft.apiData);
        if (draft.step && draft.step > 1 && draft.apiData) setStep(draft.step);
      }
    } catch { /* ignore */ }
  }, []);

  const clearDraft = () => {
    try { localStorage.removeItem(LOCAL_STORAGE_KEY); } catch { /* ignore */ }
  };

  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [toast, setToast] = useState("");

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const startLoad = async () => {
    if (!address.trim()) return;
    setLoading(true);
    setPhase(0);
    setError("");

    const phaseTimers = [1, 2, 3, 4, 5].map((p, i) =>
      setTimeout(() => setPhase(p), (i + 1) * 400)
    );

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address }),
      });

      if (res.ok) {
        const data: SearchResult = await res.json();
        setApiData(data);
      } else {
        const err = await res.json().catch(() => ({ error: "APIエラー" }));
        setError(err.error || `APIエラー (${res.status})`);
      }
    } catch {
      setError("ネットワークエラー。接続を確認してください。");
    }

    phaseTimers.forEach(clearTimeout);
    setPhase(6);
    setTimeout(() => {
      setLoading(false);
      setStep(2);
    }, 500);
  };

  const ad = apiData;
  const pTypeLabel = pType === "mansion" ? "区分マンション" : pType === "land" ? "土地" : pType === "house" ? "一戸建て" : "一棟";

  const completion = computeCompletion(formData, apiData, pType, incident);

  // CSV injection safe escape
  const csvEscape = (s: string) => `"${s.replace(/"/g, '""')}"`;

  const buildAllData = (): Partial<PropertyData> & { address: string; property_type: string } => ({
    address,
    property_type: pType,
    latitude: ad?.lat,
    longitude: ad?.lng,
    // API data
    zoning: ad?.zoning || undefined,
    building_coverage_ratio: ad?.building_coverage_ratio || undefined,
    floor_area_ratio: ad?.floor_area_ratio || undefined,
    fire_zone: ad?.fire_zone || undefined,
    urban_plan_zone: ad?.urban_plan_zone || undefined,
    height_district: ad?.height_district || undefined,
    flood_level: ad?.flood_level,
    flood_text: ad?.flood_text || undefined,
    tsunami_level: ad?.tsunami_level,
    tsunami_text: ad?.tsunami_text || undefined,
    hightide_level: ad?.hightide_level,
    hightide_text: ad?.hightide_text || undefined,
    sediment_risk: ad?.sediment_risk,
    landslide_text: ad?.landslide_text || undefined,
    school_district: ad?.school_district || undefined,
    school_district_jr: ad?.school_district_jr || undefined,
    land_price: ad?.land_price || undefined,
    land_price_year: ad?.land_price_year || undefined,
    land_price_point: ad?.land_price_point || undefined,
    future_pop: ad?.future_pop || undefined,
    future_pop_2050: ad?.future_pop_2050 || undefined,
    future_pop_change: ad?.future_pop_change || undefined,
    api_fetched_at: ad ? new Date().toISOString() : undefined,
    // Form data
    ...formData,
    is_incident: incident,
    incident_detail: incident ? formData.incident_detail : undefined,
  });

  const saveDraft = async () => {
    setSaving(true);
    try {
      const payload = buildAllData();
      const method = savedId ? "PUT" : "POST";
      const url = savedId ? `/api/properties/${savedId}` : "/api/properties";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        if (!savedId) setSavedId(data.id);
        clearDraft();
        showToast("下書きを保存しました");
      } else {
        showToast("保存に失敗しました");
      }
    } catch {
      showToast("ネットワークエラー");
    }
    setSaving(false);
  };

  const generateCSV = () => {
    const BOM = "\uFEFF";
    const rows: string[][] = [
      ["カテゴリ", "項目", "内容", "区分"],
      // 基本情報
      ["基本情報", "住所", address, "基本"],
      ["基本情報", "物件種別", pTypeLabel, "基本"],
      // 都市計画
      ["都市計画", "用途地域", ad?.zoning || "", "自動取得"],
      ["都市計画", "建ぺい率", ad?.building_coverage_ratio ? `${ad.building_coverage_ratio}%` : "", "自動取得"],
      ["都市計画", "容積率", ad?.floor_area_ratio ? `${ad.floor_area_ratio}%` : "", "自動取得"],
      ["都市計画", "防火地域", ad?.fire_zone || "", "自動取得"],
      ["都市計画", "高度地区", ad?.height_district || "", "自動取得"],
      ["都市計画", "都市計画区域区分", ad?.urban_plan_zone || "", "自動取得"],
      // ハザード
      ["ハザード", "洪水浸水想定", ad?.flood_text || "", "自動取得"],
      ["ハザード", "津波浸水想定", ad?.tsunami_text || "", "自動取得"],
      ["ハザード", "高潮浸水想定", ad?.hightide_text || "", "自動取得"],
      ["ハザード", "土砂災害警戒", ad?.landslide_text || "", "自動取得"],
      // 参考
      ["参考", "学区（小学校）", ad?.school_district || "", "自動取得"],
      ["参考", "学区（中学校）", ad?.school_district_jr || "", "自動取得"],
      ["参考", "公示地価", ad?.land_price ? `${ad.land_price}円/㎡` : "", "自動取得"],
      ["参考", "将来人口変化率", ad?.future_pop_change != null ? `${ad.future_pop_change}%（2050年）` : "", "自動取得"],
      // インフラ
      ["インフラ", "上水道", formData.water_supply || "", "手動入力"],
      ["インフラ", "下水道", formData.sewage || "", "手動入力"],
      ["インフラ", "ガス", formData.gas_type || "", "手動入力"],
      ["インフラ", "電気", formData.electricity || "", "手動入力"],
      // 道路
      ["道路", "接面道路の種別", formData.road_type || "", "手動入力"],
      ["道路", "道路幅員（m）", formData.road_width || "", "手動入力"],
      ["道路", "接道間口（m）", formData.road_frontage || "", "手動入力"],
      ["道路", "私道負担", formData.private_road || "", "手動入力"],
      // 登記
      ["登記", "所有者名", formData.owner_name || "", "手動入力"],
      ["登記", "土地面積（㎡）", formData.land_area || "", "手動入力"],
      ["登記", "建物面積（㎡）", formData.building_area || "", "手動入力"],
      ["登記", "抵当権", formData.mortgage || "", "手動入力"],
    ];

    // マンション固有
    if (pType === "mansion") {
      rows.push(
        ["管理", "管理費（月額）", formData.mgmt_fee || "", "手動入力"],
        ["管理", "修繕積立金（月額）", formData.repair_reserve || "", "手動入力"],
        ["管理", "駐車場（月額）", formData.parking_fee || "", "手動入力"],
        ["管理", "管理形態", formData.mgmt_form || "", "手動入力"],
        ["管理", "管理会社", formData.mgmt_company || "", "手動入力"],
        ["管理", "総戸数", formData.total_units || "", "手動入力"],
        ["管理", "大規模修繕予定", formData.major_repair_plan || "", "手動入力"],
      );
    }

    // 告知事項
    rows.push(
      ["告知", "心理的瑕疵（事故物件）", incident ? "あり" : "なし", "手動入力"],
    );
    if (incident) {
      rows.push(["告知", "告知事項詳細", formData.incident_detail || "", "手動入力"]);
    }
    rows.push(
      ["告知", "その他の告知事項", formData.disclosure_notes || "", "手動入力"],
      ["告知", "アスベスト調査", formData.asbestos || "", "手動入力"],
      ["告知", "耐震診断", formData.earthquake_resistance || "", "手動入力"],
    );

    // 契約
    rows.push(
      ["契約", "取引価格（円）", formData.price || "", "手動入力"],
      ["契約", "取引態様", formData.transaction_type || "", "手動入力"],
      ["契約", "手付金（円）", formData.earnest_money || "", "手動入力"],
      ["契約", "引渡予定日", formData.delivery_date || "", "手動入力"],
      ["契約", "特約事項", formData.special_terms || "", "手動入力"],
    );

    const csvContent = rows.map((r) => r.map(csvEscape).join(",")).join("\n");
    const blob = new Blob([BOM + csvContent], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `重説_${address.replace(/[/\\:*?"<>|]/g, "_") || "物件"}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("CSVをダウンロードしました");
  };

  const confirmRows: Array<{ k: string; v: string; t: "auto" | "manual" | "missing" }> = [
    // API auto
    { k: "用途地域", v: ad?.zoning || "—", t: ad?.zoning ? "auto" : "missing" },
    { k: "建ぺい率", v: ad?.building_coverage_ratio ? `${ad.building_coverage_ratio}%` : "—", t: ad?.building_coverage_ratio ? "auto" : "missing" },
    { k: "容積率", v: ad?.floor_area_ratio ? `${ad.floor_area_ratio}%` : "—", t: ad?.floor_area_ratio ? "auto" : "missing" },
    { k: "防火地域", v: ad?.fire_zone || "—", t: ad?.fire_zone ? "auto" : "missing" },
    { k: "洪水浸水想定", v: ad?.flood_text || "—", t: ad?.flood_text ? "auto" : "missing" },
    { k: "津波浸水想定", v: ad?.tsunami_text || "—", t: ad?.tsunami_text ? "auto" : "missing" },
    { k: "高潮浸水想定", v: ad?.hightide_text || "—", t: ad?.hightide_text ? "auto" : "missing" },
    { k: "土砂災害", v: ad?.landslide_text || "—", t: ad?.landslide_text ? "auto" : "missing" },
    { k: "公示地価", v: ad?.land_price ? `${ad.land_price.toLocaleString()}円/㎡` : "—", t: ad?.land_price ? "auto" : "missing" },
    // Manual
    { k: "上水道", v: formData.water_supply || "—", t: formData.water_supply ? "manual" : "missing" },
    { k: "下水道", v: formData.sewage || "—", t: formData.sewage ? "manual" : "missing" },
    { k: "ガス", v: formData.gas_type || "—", t: formData.gas_type ? "manual" : "missing" },
    { k: "接面道路", v: formData.road_type || "—", t: formData.road_type ? "manual" : "missing" },
    { k: "道路幅員", v: formData.road_width ? `${formData.road_width}m` : "—", t: formData.road_width ? "manual" : "missing" },
    { k: "所有者名", v: formData.owner_name || "—", t: formData.owner_name ? "manual" : "missing" },
    { k: "土地面積", v: formData.land_area ? `${formData.land_area}㎡` : "—", t: formData.land_area ? "manual" : "missing" },
    { k: "抵当権", v: formData.mortgage || "—", t: formData.mortgage ? "manual" : "missing" },
    { k: "取引価格", v: formData.price ? `${Number(formData.price).toLocaleString()}円` : "—", t: formData.price ? "manual" : "missing" },
    { k: "取引態様", v: formData.transaction_type || "—", t: formData.transaction_type ? "manual" : "missing" },
    { k: "アスベスト", v: formData.asbestos || "—", t: formData.asbestos ? "manual" : "missing" },
    { k: "耐震診断", v: formData.earthquake_resistance || "—", t: formData.earthquake_resistance ? "manual" : "missing" },
  ];

  if (pType === "mansion") {
    confirmRows.push(
      { k: "管理費", v: formData.mgmt_fee ? `${Number(formData.mgmt_fee).toLocaleString()}円/月` : "—", t: formData.mgmt_fee ? "manual" : "missing" },
      { k: "修繕積立金", v: formData.repair_reserve ? `${Number(formData.repair_reserve).toLocaleString()}円/月` : "—", t: formData.repair_reserve ? "manual" : "missing" },
      { k: "管理形態", v: formData.mgmt_form || "—", t: formData.mgmt_form ? "manual" : "missing" },
    );
  }

  if (incident) {
    confirmRows.push({ k: "心理的瑕疵", v: "あり", t: "manual" });
  }

  const autoCount = confirmRows.filter((r) => r.t === "auto").length;
  const manualCount = confirmRows.filter((r) => r.t === "manual").length;
  const missingCount = confirmRows.filter((r) => r.t === "missing").length;

  return (
    <div style={{ minHeight: "100vh", background: "#F1F5F9" }}>
      <Header />
      <StepNav current={step} onGo={go} canNavigate={step >= 2} />

      <main style={{ maxWidth: 740, margin: "0 auto", padding: "22px 18px 100px" }}>
        {/* Auto-save indicator */}
        {step >= 2 && (
          <div style={{
            display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 6,
            marginBottom: 8, fontSize: 11, color: "#64748B", fontWeight: 500,
          }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#86EFAC" }} />
            自動保存中（ブラウザ）
          </div>
        )}

        {/* STEP 1 */}
        {step === 1 && !loading && (
          <div className="animate-fade-in">
            <Section
              icon={MapPin}
              title="物件の所在地"
              sub="住所を入力すると、都市計画・ハザード・地価情報を自動で取得します"
            >
              <div style={{ marginBottom: 18 }}>
                <label style={{ fontSize: 13, fontWeight: 700, color: "#0F172A", display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                  物件種別
                  <span style={{ color: "#B91C1C", fontSize: 14, fontWeight: 800 }}>*</span>
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(80px, 1fr))", gap: 8 }}>
                  {PROPERTY_TYPES.map((t) => (
                    <button
                      key={t.v}
                      onClick={() => setPType(t.v)}
                      style={{
                        padding: "12px 8px",
                        borderRadius: 8,
                        cursor: "pointer",
                        textAlign: "center",
                        border: `2px solid ${pType === t.v ? "#2563EB" : "#CBD5E1"}`,
                        background: pType === t.v ? "#DBEAFE" : "#FFFFFF",
                        transition: "all 0.15s",
                      }}
                    >
                      <t.Icon
                        size={22}
                        color={pType === t.v ? "#2563EB" : "#64748B"}
                        strokeWidth={pType === t.v ? 2.2 : 1.5}
                        style={{ margin: "0 auto 6px", display: "block" }}
                      />
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: pType === t.v ? 700 : 500,
                          color: pType === t.v ? "#2563EB" : "#334155",
                        }}
                      >
                        {t.label}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ marginBottom: 20 }}>
                <label style={{ fontSize: 13, fontWeight: 700, color: "#0F172A", display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                  所在地
                  <span style={{ color: "#B91C1C", fontSize: 14, fontWeight: 800 }}>*</span>
                </label>
                <div style={{ position: "relative" }}>
                  <MapPin size={16} color="#64748B" style={{ position: "absolute", left: 12, top: 12 }} />
                  <input
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && startLoad()}
                    placeholder="例：東京都新宿区西新宿2-8-1"
                    style={{
                      width: "100%",
                      padding: "10px 12px 10px 36px",
                      borderRadius: 8,
                      border: "1.5px solid #CBD5E1",
                      fontSize: 15,
                      color: "#0F172A",
                      outline: "none",
                      boxSizing: "border-box",
                      fontWeight: 500,
                    }}
                  />
                </div>
                <div style={{ fontSize: 11, color: "#64748B", marginTop: 5, fontWeight: 500 }}>
                  番地まで入力すると取得精度が向上します
                </div>
              </div>

              <Btn onClick={startLoad} disabled={!address.trim()} full icon={Search}>
                物件情報を自動取得
              </Btn>

              {/* Restore draft notice */}
              {apiData && step === 1 && (
                <div style={{
                  marginTop: 12, padding: "10px 14px", background: "#DBEAFE",
                  border: "1.5px solid #93C5FD", borderRadius: 8, fontSize: 12, color: "#1D4ED8", fontWeight: 600,
                }}>
                  前回の入力データが復元されました。「取得結果」ステップから続行できます。
                </div>
              )}
            </Section>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr 1fr",
                gap: 10,
                padding: 16,
                background: "#FFFFFF",
                border: "1px solid #CBD5E1",
                borderRadius: 10,
                boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
              }}
            >
              {[
                { Icon: Shield, label: "都市計画", src: "不動産情報ライブラリ", official: true },
                { Icon: Droplets, label: "ハザード", src: "ハザードAPI", official: false },
                { Icon: DollarSign, label: "地価情報", src: "国土交通省", official: true },
              ].map((s) => (
                <div
                  key={s.label}
                  style={{ textAlign: "center", padding: "10px 8px", background: "#F8FAFC", borderRadius: 8 }}
                >
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 8,
                      background: "#1a3a5c",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      marginBottom: 6,
                    }}
                  >
                    <s.Icon size={18} color="#FFF" strokeWidth={2} />
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#0F172A" }}>{s.label}</div>
                  <div style={{ marginTop: 4 }}>
                    <DataSourceBadge source={s.src} official={s.official} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <Section icon={Database} title="物件情報を取得中" sub={address}>
            <div style={{ maxWidth: 340 }}>
              <LoadingLine label="ジオコーディング" done={phase > 1} active={phase === 1} />
              <LoadingLine label="用途地域・建ぺい率" done={phase > 2} active={phase === 2} />
              <LoadingLine label="防火地域" done={phase > 3} active={phase === 3} />
              <LoadingLine label="ハザード情報" done={phase > 4} active={phase === 4} />
              <LoadingLine label="地価・学区" done={phase > 5} active={phase === 5} />
              <LoadingLine label="データ統合完了" done={phase >= 6} active={false} />
            </div>
            <div
              style={{
                marginTop: 18,
                background: "#E2E8F0",
                borderRadius: 6,
                height: 6,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  background: "linear-gradient(90deg, #2563EB, #166534)",
                  borderRadius: 6,
                  width: `${(phase / 6) * 100}%`,
                  transition: "width 0.4s",
                }}
              />
            </div>
          </Section>
        )}

        {/* STEP 2 */}
        {step === 2 && (
          <div className="animate-fade-in">
            <ProgressBar percent={completion.percent} />

            {error ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 12,
                  padding: "14px 18px",
                  background: "#FEE2E2",
                  border: "1.5px solid #FCA5A5",
                  borderRadius: 8,
                  marginBottom: 16,
                }}
              >
                <AlertTriangle size={20} color="#B91C1C" strokeWidth={2.5} style={{ flexShrink: 0, marginTop: 2 }} />
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "#B91C1C" }}>
                    API取得エラー
                  </div>
                  <div style={{ fontSize: 12, color: "#B91C1C", marginTop: 2, fontWeight: 500 }}>
                    {error}
                  </div>
                  <div style={{ fontSize: 11, color: "#991B1B", marginTop: 6, fontWeight: 500 }}>
                    住所の表記を確認するか、しばらく時間をおいて再取得してください。手動入力で続行することも可能です。
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Btn variant="secondary" onClick={() => go(1)} icon={ChevronLeft}>住所を修正して再取得</Btn>
                  </div>
                </div>
              </div>
            ) : (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "14px 18px",
                  background: "#DCFCE7",
                  border: "1.5px solid #86EFAC",
                  borderRadius: 8,
                  marginBottom: 16,
                }}
              >
                <CheckCircle2 size={20} color="#166534" strokeWidth={2.5} />
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "#14532D" }}>
                    情報を自動取得しました{ad?.elapsed_ms ? `（${(ad.elapsed_ms / 1000).toFixed(1)}秒）` : ""}
                  </div>
                  <div style={{ fontSize: 12, color: "#334155", marginTop: 2, fontWeight: 500 }}>
                    手動調査 約2時間 → 自動取得で数秒に短縮
                  </div>
                </div>
              </div>
            )}

            <Section icon={Shield} title="都市計画情報" sub="不動産情報ライブラリ API">
              <div style={{ marginBottom: 8 }}>
                <DataSourceBadge source="不動産情報ライブラリ（国土交通省）" official={true} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <AutoRow label="用途地域" value={ad?.zoning || "該当データなし"} />
                <AutoRow label="防火地域" value={ad?.fire_zone || "該当データなし"} />
                <AutoRow label="建ぺい率" value={ad?.building_coverage_ratio ? `${ad.building_coverage_ratio}%` : "該当データなし"} />
                <AutoRow label="容積率" value={ad?.floor_area_ratio ? `${ad.floor_area_ratio}%` : "該当データなし"} />
                <AutoRow label="高度地区" value={ad?.height_district || "該当データなし"} />
                <AutoRow label="学区（小学校）" value={ad?.school_district || "該当データなし"} />
              </div>
            </Section>

            <Section icon={Droplets} title="ハザード情報" sub="ハザードAPI（東海大学）">
              <div style={{ marginBottom: 8 }}>
                <DataSourceBadge source="ハザードマップAPI（サードパーティ）" official={false} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <AutoRow label="洪水浸水想定" value={ad?.flood_text || "該当データなし"} sub={ad?.flood_river ? `対象河川: ${ad.flood_river}` : undefined} />
                <AutoRow label="土砂災害警戒" value={ad?.landslide_text || "該当データなし"} />
                <AutoRow label="津波浸水想定" value={ad?.tsunami_text || "該当データなし"} />
                <AutoRow label="高潮浸水想定" value={ad?.hightide_text || "該当データなし"} />
              </div>
            </Section>

            <Section icon={DollarSign} title="地価・人口">
              <div style={{ marginBottom: 8 }}>
                <DataSourceBadge source="国土交通省 地価公示" official={true} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <AutoRow
                  label="公示地価（最寄地点）"
                  value={ad?.land_price ? `${ad.land_price.toLocaleString()}円/㎡` : "該当データなし"}
                  sub={ad?.land_price_year ? `${ad.land_price_year}年 ${ad.land_price_point || ""}` : undefined}
                />
                <AutoRow
                  label="将来人口推計"
                  value={ad?.future_pop_change != null ? `${ad.future_pop_change}%（2050年）` : "該当データなし"}
                  sub={
                    ad?.future_pop && ad?.future_pop_2050
                      ? `${ad.future_pop.toLocaleString()}人 → ${ad.future_pop_2050.toLocaleString()}人`
                      : undefined
                  }
                />
              </div>
            </Section>

            <div style={{ display: "flex", gap: 10 }}>
              <Btn variant="secondary" onClick={() => go(1)} icon={ChevronLeft}>住所修正</Btn>
              <div style={{ flex: 1 }}>
                <Btn full onClick={() => go(3)} icon={ArrowRight}>次へ：インフラ・登記情報</Btn>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3 */}
        {step === 3 && (
          <div className="animate-fade-in">
            <ProgressBar percent={completion.percent} />

            <Section icon={Plug} title="インフラ設備" sub="手動入力が必要な項目です">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <Field label="上水道" options={["公営水道", "井戸水", "受水槽", "その他"]} half value={formData.water_supply} onChange={(v) => updateForm("water_supply", v)} required />
                <Field label="下水道" options={["公共下水", "浄化槽（個別）", "浄化槽（集中）", "汲み取り"]} half value={formData.sewage} onChange={(v) => updateForm("sewage", v)} required />
                <Field label="ガス" options={["都市ガス", "プロパン（個別）", "プロパン（集中）", "オール電化"]} half value={formData.gas_type} onChange={(v) => updateForm("gas_type", v)} required />
                <Field label="電気" placeholder="例：東京電力EP 40A" half value={formData.electricity} onChange={(v) => updateForm("electricity", v)} />
              </div>
            </Section>

            <Section icon={Route} title="道路関係">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <Field
                  label="接面道路の種別"
                  required
                  options={["42条1項1号（公道）", "42条1項2号（開発）", "42条1項3号（既存）", "42条1項5号（位置指定）"]}
                  value={formData.road_type}
                  onChange={(v) => updateForm("road_type", v)}
                />
                <div>
                  <Field label="道路幅員（m）" placeholder="例：6.0" type="number" half value={formData.road_width} onChange={(v) => updateForm("road_width", v)} required />
                  <NumericValidation value={formData.road_width} />
                </div>
                <div>
                  <Field label="接道間口（m）" placeholder="例：8.5" type="number" half value={formData.road_frontage} onChange={(v) => updateForm("road_frontage", v)} />
                  <NumericValidation value={formData.road_frontage} />
                </div>
                <Field label="私道負担" options={["なし", "あり"]} half value={formData.private_road} onChange={(v) => updateForm("private_road", v)} />
              </div>
            </Section>

            <Section icon={FileText} title="登記情報">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <Field label="所有者名" placeholder="例：山田太郎" required value={formData.owner_name} onChange={(v) => updateForm("owner_name", v)} />
                <div>
                  <Field label="土地面積（㎡）" placeholder="例：120.50" type="number" half value={formData.land_area} onChange={(v) => updateForm("land_area", v)} />
                  <NumericValidation value={formData.land_area} />
                </div>
                <div>
                  <Field label="建物面積（㎡）" placeholder="例：98.76" type="number" half value={formData.building_area} onChange={(v) => updateForm("building_area", v)} />
                  <NumericValidation value={formData.building_area} />
                </div>
                <Field label="抵当権" required options={["なし", "あり（抹消予定）", "あり（残置）"]} value={formData.mortgage} onChange={(v) => updateForm("mortgage", v)} />
              </div>
            </Section>

            {pType === "mansion" && (
              <Section icon={Building2} title="マンション固有情報" sub="区分マンションの場合のみ表示">
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                  <div>
                    <Field label="管理費（月額）" placeholder="15,000" type="number" required half value={formData.mgmt_fee} onChange={(v) => updateForm("mgmt_fee", v)} />
                    <NumericValidation value={formData.mgmt_fee} />
                  </div>
                  <div>
                    <Field label="修繕積立金（月額）" placeholder="12,000" type="number" required half value={formData.repair_reserve} onChange={(v) => updateForm("repair_reserve", v)} />
                    <NumericValidation value={formData.repair_reserve} />
                  </div>
                  <div>
                    <Field label="駐車場（月額）" placeholder="20,000" type="number" half value={formData.parking_fee} onChange={(v) => updateForm("parking_fee", v)} />
                    <NumericValidation value={formData.parking_fee} />
                  </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
                  <Field label="管理形態" options={["全部委託", "一部委託", "自主管理"]} half value={formData.mgmt_form} onChange={(v) => updateForm("mgmt_form", v)} required />
                  <Field label="管理会社名" placeholder="例：三井不動産レジデンシャル" half value={formData.mgmt_company} onChange={(v) => updateForm("mgmt_company", v)} />
                  <div>
                    <Field label="総戸数" placeholder="例：120" type="number" half value={formData.total_units} onChange={(v) => updateForm("total_units", v)} />
                    <NumericValidation value={formData.total_units} />
                  </div>
                  <Field label="大規模修繕予定" placeholder="例：2026年外壁改修" half value={formData.major_repair_plan} onChange={(v) => updateForm("major_repair_plan", v)} />
                </div>
              </Section>
            )}

            <div style={{ display: "flex", gap: 10 }}>
              <Btn variant="secondary" onClick={() => go(2)} icon={ChevronLeft}>戻る</Btn>
              <div style={{ flex: 1 }}>
                <Btn full onClick={() => go(4)} icon={ArrowRight}>次へ：告知・契約条件</Btn>
              </div>
            </div>
          </div>
        )}

        {/* STEP 4 */}
        {step === 4 && (
          <div className="animate-fade-in">
            <ProgressBar percent={completion.percent} />

            <Section icon={TriangleAlert} title="物件告知事項" sub="売主からの告知内容">
              <div
                onClick={() => setIncident(!incident)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "12px 16px",
                  borderRadius: 8,
                  cursor: "pointer",
                  marginBottom: 16,
                  border: `2px solid ${incident ? "#B91C1C" : "#CBD5E1"}`,
                  background: incident ? "#FEE2E2" : "#FFFFFF",
                  transition: "all 0.15s",
                }}
              >
                <div
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: 4,
                    flexShrink: 0,
                    border: `2px solid ${incident ? "#B91C1C" : "#64748B"}`,
                    background: incident ? "#B91C1C" : "#FFFFFF",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {incident && <Check size={14} color="#FFF" strokeWidth={3} />}
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: incident ? "#B91C1C" : "#0F172A" }}>
                    心理的瑕疵あり（事故物件）
                  </div>
                  <div style={{ fontSize: 11, color: "#64748B", fontWeight: 500, marginTop: 1 }}>
                    自殺・他殺・事故死・火災等の告知事項がある場合
                  </div>
                </div>
              </div>

              {incident && (
                <div
                  style={{
                    padding: 14,
                    borderRadius: 8,
                    border: "1.5px solid #FCA5A5",
                    background: "#FEE2E2",
                    marginBottom: 16,
                  }}
                  className="animate-fade-in"
                >
                  <label
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: "#B91C1C",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      marginBottom: 8,
                    }}
                  >
                    <AlertTriangle size={14} /> 告知事項の詳細
                    <span style={{ color: "#B91C1C", fontSize: 14, fontWeight: 800 }}>*</span>
                  </label>
                  <textarea
                    placeholder="例：2020年○月、前所有者が室内で病死。発見まで約1週間。特殊清掃済み。"
                    rows={3}
                    value={formData.incident_detail || ""}
                    onChange={(e) => updateForm("incident_detail", e.target.value)}
                    style={{
                      width: "100%",
                      padding: "10px 12px",
                      borderRadius: 6,
                      fontSize: 13,
                      border: "1.5px solid #FCA5A5",
                      outline: "none",
                      resize: "vertical",
                      fontFamily: "inherit",
                      boxSizing: "border-box",
                    }}
                  />
                </div>
              )}

              <div style={{ display: "grid", gap: 12 }}>
                <Field label="その他の告知事項" type="textarea" placeholder="例：近隣に墓地あり（南側約50m）" value={formData.disclosure_notes} onChange={(v) => updateForm("disclosure_notes", v)} />
                <Field label="アスベスト調査" required options={["調査済み（使用なし）", "調査済み（使用あり）", "未調査"]} value={formData.asbestos} onChange={(v) => updateForm("asbestos", v)} />
                <Field label="耐震診断" required options={["実施済み（適合）", "実施済み（不適合）", "未実施"]} value={formData.earthquake_resistance} onChange={(v) => updateForm("earthquake_resistance", v)} />
              </div>
            </Section>

            <Section icon={Scale} title="取引・契約条件">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <Field label="取引価格（円）" placeholder="例：45000000" type="number" required value={formData.price} onChange={(v) => updateForm("price", v)} />
                  <NumericValidation value={formData.price} />
                </div>
                <Field label="取引態様" required options={["売主", "代理", "媒介（専属専任）", "媒介（専任）", "媒介（一般）"]} value={formData.transaction_type} onChange={(v) => updateForm("transaction_type", v)} />
                <div>
                  <Field label="手付金（円）" placeholder="例：4500000" type="number" half value={formData.earnest_money} onChange={(v) => updateForm("earnest_money", v)} />
                  <NumericValidation value={formData.earnest_money} />
                </div>
                <Field label="引渡予定日" type="date" half value={formData.delivery_date} onChange={(v) => updateForm("delivery_date", v)} />
                <Field label="特約事項" type="textarea" placeholder="例：ローン特約あり（2026年3月15日まで）" value={formData.special_terms} onChange={(v) => updateForm("special_terms", v)} />
              </div>
            </Section>

            <div style={{ display: "flex", gap: 10 }}>
              <Btn variant="secondary" onClick={() => go(3)} icon={ChevronLeft}>戻る</Btn>
              <div style={{ flex: 1 }}>
                <Btn full onClick={() => go(5)} icon={ClipboardCheck}>確認画面へ</Btn>
              </div>
            </div>
          </div>
        )}

        {/* STEP 5 */}
        {step === 5 && (
          <div className="animate-fade-in">
            <ProgressBar percent={completion.percent} />

            <Section icon={ClipboardCheck} title="入力内容の確認">
              <div
                style={{
                  padding: "14px 16px",
                  background: "#F8FAFC",
                  borderRadius: 8,
                  border: "1.5px solid #E2E8F0",
                  marginBottom: 16,
                }}
              >
                <div style={{ fontSize: 11, color: "#64748B", fontWeight: 600 }}>対象物件</div>
                <div style={{ fontSize: 17, fontWeight: 700, color: "#1a3a5c", marginTop: 3 }}>
                  {address || "住所未入力"}
                </div>
                <div style={{ fontSize: 12, color: "#334155", marginTop: 3, fontWeight: 600 }}>
                  {pType === "mansion" ? "区分マンション" : pType === "land" ? "土地" : pType === "house" ? "一戸建て" : "一棟"}
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 16 }}>
                {[
                  { n: autoCount, label: "API自動取得", color: "#166534", bg: "#DCFCE7", border: "#86EFAC" },
                  { n: manualCount, label: "手動入力済", color: "#854D0E", bg: "#FEF9C3", border: "#FDE047" },
                  { n: missingCount, label: "未入力", color: "#B91C1C", bg: "#FEE2E2", border: "#FCA5A5" },
                ].map((s) => (
                  <div
                    key={s.label}
                    style={{
                      textAlign: "center",
                      padding: "14px 8px",
                      borderRadius: 8,
                      background: s.bg,
                      border: `1.5px solid ${s.border}`,
                    }}
                  >
                    <div style={{ fontSize: 26, fontWeight: 800, color: s.color }}>{s.n}</div>
                    <div style={{ fontSize: 11, color: s.color, fontWeight: 700 }}>{s.label}</div>
                  </div>
                ))}
              </div>

              <div style={{ border: "1.5px solid #CBD5E1", borderRadius: 8, overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: "#1E293B" }}>
                      <th style={{ padding: "10px 14px", textAlign: "left", color: "#F1F5F9", fontWeight: 600, fontSize: 12 }}>項目</th>
                      <th style={{ padding: "10px 14px", textAlign: "left", color: "#F1F5F9", fontWeight: 600, fontSize: 12 }}>内容</th>
                      <th style={{ padding: "10px 14px", textAlign: "center", color: "#F1F5F9", fontWeight: 600, fontSize: 12, width: 80 }}>区分</th>
                    </tr>
                  </thead>
                  <tbody>
                    {confirmRows.map((r, i) => (
                      <tr
                        key={i}
                        style={{
                          borderBottom: "1px solid #E2E8F0",
                          background: r.t === "missing" ? "#FEE2E2" : i % 2 ? "#F8FAFC" : "#FFFFFF",
                        }}
                      >
                        <td style={{ padding: "9px 14px", fontWeight: 600, color: "#0F172A" }}>{r.k}</td>
                        <td
                          style={{
                            padding: "9px 14px",
                            fontWeight: 500,
                            color: r.t === "missing" ? "#B91C1C" : "#0F172A",
                          }}
                        >
                          {r.v}
                        </td>
                        <td style={{ padding: "9px 14px", textAlign: "center" }}>
                          <Tag variant={r.t}>
                            {r.t === "auto" ? "自動" : r.t === "manual" ? "手動" : "未入力"}
                          </Tag>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div
                  style={{
                    padding: "8px 14px",
                    background: "#F8FAFC",
                    fontSize: 10,
                    color: "#64748B",
                    textAlign: "center",
                    fontWeight: 500,
                    borderTop: "1px solid #E2E8F0",
                  }}
                >
                  抜粋表示 — CSV出力時は全項目を含みます
                </div>
              </div>
            </Section>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
              <Btn variant="secondary" full icon={Save} onClick={saveDraft} disabled={saving}>
                {saving ? "保存中..." : savedId ? "上書き保存" : "ドラフト保存"}
              </Btn>
              <Btn variant="success" full icon={Download} onClick={generateCSV}>CSV出力</Btn>
            </div>
            <Btn variant="secondary" full onClick={() => go(4)} icon={ChevronLeft}>入力に戻る</Btn>
          </div>
        )}
      </main>

      {/* Toast notification */}
      {toast && (
        <div
          style={{
            position: "fixed",
            bottom: 24,
            left: "50%",
            transform: "translateX(-50%)",
            background: "#1E293B",
            color: "#F8FAFC",
            padding: "12px 24px",
            borderRadius: 8,
            fontSize: 14,
            fontWeight: 600,
            boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
            zIndex: 1000,
          }}
        >
          {toast}
        </div>
      )}
    </div>
  );
}
