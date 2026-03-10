"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Header from "@/components/Header";
import Section from "@/components/ui/Section";
import AutoRow from "@/components/ui/AutoRow";
import Btn from "@/components/ui/Btn";
import Tag from "@/components/ui/Tag";
import {
  FileText, ChevronLeft, Download, RefreshCw,
  Shield, Droplets, Plug, Route, Building2,
  TriangleAlert, Scale, Loader2,
} from "lucide-react";
import Link from "next/link";
import type { PropertyData } from "@/lib/types";

type DetailRow = { label: string; value: string; category?: string };

export default function PropertyDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [property, setProperty] = useState<PropertyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState("");
  const [fetchError, setFetchError] = useState("");

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const loadProperty = () => {
    fetch(`/api/properties/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then((data) => {
        if (data.error) {
          setProperty(null);
          setFetchError(data.error);
        } else {
          setProperty(data);
        }
        setLoading(false);
      })
      .catch(() => {
        setFetchError("読み込みに失敗しました");
        setLoading(false);
      });
  };

  useEffect(() => { loadProperty(); }, [id]);

  const refreshApi = async () => {
    if (!property?.address) return;
    setRefreshing(true);
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address: property.address }),
      });
      if (res.ok) {
        const apiData = await res.json();
        const updateRes = await fetch(`/api/properties/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            zoning: apiData.zoning,
            building_coverage_ratio: apiData.building_coverage_ratio,
            floor_area_ratio: apiData.floor_area_ratio,
            fire_zone: apiData.fire_zone,
            height_district: apiData.height_district,
            urban_plan_zone: apiData.urban_plan_zone,
            flood_level: apiData.flood_level,
            flood_text: apiData.flood_text,
            tsunami_level: apiData.tsunami_level,
            tsunami_text: apiData.tsunami_text,
            hightide_level: apiData.hightide_level,
            hightide_text: apiData.hightide_text,
            sediment_risk: apiData.sediment_risk,
            landslide_text: apiData.landslide_text,
            school_district: apiData.school_district,
            school_district_jr: apiData.school_district_jr,
            land_price: apiData.land_price,
            land_price_year: apiData.land_price_year,
            land_price_point: apiData.land_price_point,
            future_pop: apiData.future_pop,
            future_pop_2050: apiData.future_pop_2050,
            future_pop_change: apiData.future_pop_change,
            api_fetched_at: new Date().toISOString(),
          }),
        });
        if (updateRes.ok) {
          const updated = await updateRes.json();
          setProperty(updated);
          showToast("API情報を再取得しました");
        }
      } else {
        showToast("API取得に失敗しました");
      }
    } catch {
      showToast("ネットワークエラー");
    }
    setRefreshing(false);
  };

  const csvEscape = (s: string) => `"${s.replace(/"/g, '""')}"`;

  const generateCSV = () => {
    if (!property) return;
    const p = property;
    const pTypeLabel = p.property_type === "mansion" ? "区分マンション" : p.property_type === "land" ? "土地" : p.property_type === "house" ? "一戸建て" : "一棟";
    const BOM = "\uFEFF";
    const rows: string[][] = [
      ["カテゴリ", "項目", "内容", "区分"],
      ["基本情報", "住所", p.address, "基本"],
      ["基本情報", "物件種別", pTypeLabel, "基本"],
      ["都市計画", "用途地域", p.zoning || "", "自動取得"],
      ["都市計画", "建ぺい率", p.building_coverage_ratio ? `${p.building_coverage_ratio}%` : "", "自動取得"],
      ["都市計画", "容積率", p.floor_area_ratio ? `${p.floor_area_ratio}%` : "", "自動取得"],
      ["都市計画", "防火地域", p.fire_zone || "", "自動取得"],
      ["都市計画", "高度地区", p.height_district || "", "自動取得"],
      ["都市計画", "都市計画区域区分", p.urban_plan_zone || "", "自動取得"],
      ["ハザード", "洪水浸水想定", p.flood_text || "", "自動取得"],
      ["ハザード", "津波浸水想定", p.tsunami_text || "", "自動取得"],
      ["ハザード", "高潮浸水想定", p.hightide_text || "", "自動取得"],
      ["ハザード", "土砂災害警戒", p.landslide_text || "", "自動取得"],
      ["参考", "学区（小学校）", p.school_district || "", "自動取得"],
      ["参考", "学区（中学校）", p.school_district_jr || "", "自動取得"],
      ["参考", "公示地価", p.land_price ? `${p.land_price}円/㎡` : "", "自動取得"],
      ["インフラ", "上水道", p.water_supply || "", "手動入力"],
      ["インフラ", "下水道", p.sewage || "", "手動入力"],
      ["インフラ", "ガス", p.gas_type || "", "手動入力"],
      ["インフラ", "電気", p.electricity || "", "手動入力"],
      ["道路", "接面道路の種別", p.road_type || "", "手動入力"],
      ["道路", "道路幅員（m）", p.road_width || "", "手動入力"],
      ["道路", "接道間口（m）", p.road_frontage || "", "手動入力"],
      ["道路", "私道負担", p.private_road || "", "手動入力"],
      ["登記", "所有者名", p.owner_name || "", "手動入力"],
      ["登記", "土地面積（㎡）", p.land_area || "", "手動入力"],
      ["登記", "建物面積（㎡）", p.building_area || "", "手動入力"],
      ["登記", "抵当権", p.mortgage || "", "手動入力"],
    ];
    if (p.property_type === "mansion") {
      rows.push(
        ["管理", "管理費（月額）", p.mgmt_fee || "", "手動入力"],
        ["管理", "修繕積立金（月額）", p.repair_reserve || "", "手動入力"],
        ["管理", "駐車場（月額）", p.parking_fee || "", "手動入力"],
        ["管理", "管理形態", p.mgmt_form || "", "手動入力"],
        ["管理", "管理会社", p.mgmt_company || "", "手動入力"],
        ["管理", "総戸数", p.total_units || "", "手動入力"],
        ["管理", "大規模修繕予定", p.major_repair_plan || "", "手動入力"],
      );
    }
    rows.push(
      ["告知", "心理的瑕疵", p.is_incident ? "あり" : "なし", "手動入力"],
      ["告知", "告知事項詳細", p.incident_detail || "", "手動入力"],
      ["告知", "その他の告知事項", p.disclosure_notes || "", "手動入力"],
      ["告知", "アスベスト調査", p.asbestos || "", "手動入力"],
      ["告知", "耐震診断", p.earthquake_resistance || "", "手動入力"],
      ["契約", "取引価格（円）", p.price || "", "手動入力"],
      ["契約", "取引態様", p.transaction_type || "", "手動入力"],
      ["契約", "手付金（円）", p.earnest_money || "", "手動入力"],
      ["契約", "引渡予定日", p.delivery_date || "", "手動入力"],
      ["契約", "特約事項", p.special_terms || "", "手動入力"],
    );
    const csvContent = rows.map((r) => r.map(csvEscape).join(",")).join("\n");
    const blob = new Blob([BOM + csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `重説_${p.address.replace(/[/\\:*?"<>|]/g, "_")}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("CSVをダウンロードしました");
  };

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "#F1F5F9" }}>
        <Header />
        <main style={{ maxWidth: 740, margin: "0 auto", padding: "22px 18px" }}>
          <div style={{ textAlign: "center", padding: 60, color: "#64748B" }}>
            <Loader2 size={24} className="animate-spin-slow" style={{ margin: "0 auto 12px", display: "block" }} />
            読み込み中...
          </div>
        </main>
      </div>
    );
  }

  if (!property || fetchError) {
    return (
      <div style={{ minHeight: "100vh", background: "#F1F5F9" }}>
        <Header />
        <main style={{ maxWidth: 740, margin: "0 auto", padding: "22px 18px" }}>
          <Section icon={FileText} title="物件が見つかりません">
            <div style={{ textAlign: "center", padding: 30 }}>
              <div style={{ fontSize: 13, color: "#64748B", marginBottom: 16 }}>
                {fetchError || "この物件は存在しないか、削除されました。"}
              </div>
              <Link href="/dashboard"><Btn icon={ChevronLeft}>ダッシュボードに戻る</Btn></Link>
            </div>
          </Section>
        </main>
      </div>
    );
  }

  const p = property;
  const str = (v: unknown) => (v != null && v !== "" ? String(v) : "—");
  const pTypeLabel = p.property_type === "mansion" ? "区分マンション" : p.property_type === "land" ? "土地" : p.property_type === "house" ? "一戸建て" : "一棟";

  const autoRows: DetailRow[] = [
    { label: "用途地域", value: str(p.zoning) },
    { label: "建ぺい率", value: p.building_coverage_ratio ? `${p.building_coverage_ratio}%` : "—" },
    { label: "容積率", value: p.floor_area_ratio ? `${p.floor_area_ratio}%` : "—" },
    { label: "防火地域", value: str(p.fire_zone) },
    { label: "高度地区", value: str(p.height_district) },
    { label: "都市計画区域", value: str(p.urban_plan_zone) },
  ];

  const hazardRows: DetailRow[] = [
    { label: "洪水浸水想定", value: str(p.flood_text) },
    { label: "津波浸水想定", value: str(p.tsunami_text) },
    { label: "高潮浸水想定", value: str(p.hightide_text) },
    { label: "土砂災害警戒", value: str(p.landslide_text) },
  ];

  const infraRows: DetailRow[] = [
    { label: "上水道", value: str(p.water_supply) },
    { label: "下水道", value: str(p.sewage) },
    { label: "ガス", value: str(p.gas_type) },
    { label: "電気", value: str(p.electricity) },
    { label: "接面道路", value: str(p.road_type) },
    { label: "道路幅員", value: p.road_width ? `${p.road_width}m` : "—" },
    { label: "私道負担", value: str(p.private_road) },
  ];

  const regRows: DetailRow[] = [
    { label: "所有者名", value: str(p.owner_name) },
    { label: "土地面積", value: p.land_area ? `${p.land_area}㎡` : "—" },
    { label: "建物面積", value: p.building_area ? `${p.building_area}㎡` : "—" },
    { label: "抵当権", value: str(p.mortgage) },
  ];

  const contractRows: DetailRow[] = [
    { label: "取引価格", value: p.price ? `${Number(p.price).toLocaleString()}円` : "—" },
    { label: "取引態様", value: str(p.transaction_type) },
    { label: "手付金", value: p.earnest_money ? `${Number(p.earnest_money).toLocaleString()}円` : "—" },
    { label: "引渡予定日", value: str(p.delivery_date) },
  ];

  const renderRows = (rows: DetailRow[], isAuto: boolean) => (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
      {rows.map((r) =>
        isAuto ? (
          <AutoRow key={r.label} label={r.label} value={r.value} />
        ) : (
          <div
            key={r.label}
            style={{
              padding: "12px 16px",
              background: r.value !== "—" ? "#FEF9C3" : "#F8FAFC",
              borderRadius: 8,
              border: `1.5px solid ${r.value !== "—" ? "#FDE047" : "#E2E8F0"}`,
            }}
          >
            <div style={{ fontSize: 11, color: "#64748B", marginBottom: 3, fontWeight: 600 }}>{r.label}</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: r.value !== "—" ? "#854D0E" : "#94A3B8" }}>{r.value}</div>
          </div>
        )
      )}
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: "#F1F5F9" }}>
      <Header />
      <main style={{ maxWidth: 740, margin: "0 auto", padding: "22px 18px 100px" }}>
        <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 10 }}>
          <Link href="/dashboard" style={{ textDecoration: "none" }}>
            <Btn variant="secondary" icon={ChevronLeft}>戻る</Btn>
          </Link>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#0F172A" }}>{p.address}</div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 4 }}>
              <Tag variant="manual">{pTypeLabel}</Tag>
              <Tag variant={p.status === "completed" ? "auto" : "missing"}>
                {p.status === "completed" ? "完了" : "下書き"}
              </Tag>
            </div>
          </div>
        </div>

        <Section icon={Shield} title="都市計画情報">
          {renderRows(autoRows, true)}
        </Section>

        <Section icon={Droplets} title="ハザード情報">
          {renderRows(hazardRows, true)}
        </Section>

        <Section icon={Plug} title="インフラ・道路">
          {renderRows(infraRows, false)}
        </Section>

        <Section icon={FileText} title="登記情報">
          {renderRows(regRows, false)}
        </Section>

        {p.property_type === "mansion" && (
          <Section icon={Building2} title="マンション管理">
            {renderRows([
              { label: "管理費", value: p.mgmt_fee ? `${Number(p.mgmt_fee).toLocaleString()}円/月` : "—" },
              { label: "修繕積立金", value: p.repair_reserve ? `${Number(p.repair_reserve).toLocaleString()}円/月` : "—" },
              { label: "管理形態", value: str(p.mgmt_form) },
              { label: "管理会社", value: str(p.mgmt_company) },
              { label: "総戸数", value: p.total_units ? `${p.total_units}戸` : "—" },
              { label: "大規模修繕", value: str(p.major_repair_plan) },
            ], false)}
          </Section>
        )}

        {(p.is_incident || p.disclosure_notes || p.asbestos || p.earthquake_resistance) && (
          <Section icon={TriangleAlert} title="告知事項">
            <div style={{ display: "grid", gap: 10 }}>
              {p.is_incident && (
                <div style={{ padding: "12px 16px", background: "#FEE2E2", borderRadius: 8, border: "1.5px solid #FCA5A5" }}>
                  <div style={{ fontSize: 11, color: "#B91C1C", fontWeight: 700, marginBottom: 4 }}>心理的瑕疵あり</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "#B91C1C" }}>{p.incident_detail || "詳細なし"}</div>
                </div>
              )}
              {renderRows([
                { label: "その他告知", value: str(p.disclosure_notes) },
                { label: "アスベスト", value: str(p.asbestos) },
                { label: "耐震診断", value: str(p.earthquake_resistance) },
              ], false)}
            </div>
          </Section>
        )}

        <Section icon={Scale} title="契約条件">
          {renderRows(contractRows, false)}
          {p.special_terms && (
            <div style={{ marginTop: 10, padding: "12px 16px", background: "#FEF9C3", borderRadius: 8, border: "1.5px solid #FDE047" }}>
              <div style={{ fontSize: 11, color: "#64748B", fontWeight: 600, marginBottom: 4 }}>特約事項</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#854D0E", whiteSpace: "pre-wrap" }}>{p.special_terms}</div>
            </div>
          )}
        </Section>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <Btn variant="secondary" full icon={RefreshCw} onClick={refreshApi} disabled={refreshing}>
            {refreshing ? "取得中..." : "API再取得"}
          </Btn>
          <Btn variant="success" full icon={Download} onClick={generateCSV}>CSV出力</Btn>
        </div>
      </main>

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
