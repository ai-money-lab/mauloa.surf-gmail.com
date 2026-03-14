"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Header from "@/components/Header";
import Section from "@/components/ui/Section";
import AutoRow from "@/components/ui/AutoRow";
import Btn from "@/components/ui/Btn";
import Tag from "@/components/ui/Tag";
import Field from "@/components/ui/Field";
import {
  FileText, ChevronLeft, Download, RefreshCw,
  Shield, Droplets, Plug, Route, Building2,
  TriangleAlert, Scale, Loader2, Trash2, Pencil,
  Eye, Printer, X, AlertTriangle, Upload, ClipboardCheck, Clock,
} from "lucide-react";
import PdfExtractor from "@/components/PdfExtractor";
import Link from "next/link";
import type { PropertyData, SearchResult } from "@/lib/types";

type DetailRow = { label: string; value: string; field?: string; category?: string };

function computeCompletionForProperty(p: Record<string, unknown>): { filled: number; total: number; percent: number } {
  const fields: boolean[] = [
    !!p.zoning, !!p.building_coverage_ratio, !!p.floor_area_ratio, !!p.fire_zone,
    !!p.flood_text, !!p.tsunami_text, !!p.hightide_text, !!p.landslide_text, !!p.land_price,
    !!p.water_supply, !!p.sewage, !!p.gas_type, !!p.electricity,
    !!p.road_type, !!p.road_width, !!p.owner_name, !!p.land_area,
    !!p.mortgage, !!p.price, !!p.transaction_type, !!p.asbestos, !!p.earthquake_resistance,
  ];
  if (p.property_type === "mansion") {
    fields.push(!!p.mgmt_fee, !!p.repair_reserve, !!p.mgmt_form);
  }
  const filled = fields.filter(Boolean).length;
  const total = fields.length;
  return { filled, total, percent: total > 0 ? Math.round((filled / total) * 100) : 0 };
}

function ProgressBar({ percent }: { percent: number }) {
  const color = percent >= 80 ? "#166534" : percent >= 50 ? "#854D0E" : "#B91C1C";
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color }}>入力完了率</span>
        <span style={{ fontSize: 13, fontWeight: 800, color }}>{percent}%</span>
      </div>
      <div style={{ background: "#E2E8F0", borderRadius: 6, height: 8, overflow: "hidden" }}>
        <div style={{ height: "100%", background: color, borderRadius: 6, width: `${percent}%`, transition: "width 0.4s" }} />
      </div>
    </div>
  );
}

function MissingFieldIndicator({ value, label }: { value: string; label: string }) {
  if (value !== "\u2014") return null;
  return (
    <span style={{ fontSize: 10, color: "#B91C1C", fontWeight: 600, marginLeft: 6 }}>
      ({label}未入力)
    </span>
  );
}

/* ─── 法定記載事項チェックリスト ─── */
function LegalChecklist({ property: p, isRental }: { property: PropertyData; isRental: boolean }) {
  const [open, setOpen] = useState(false);
  const isMansion = p.property_type === "mansion" || p.property_type === "condo";

  type CheckItem = { label: string; ok: boolean; required: boolean; section: string };
  const items: CheckItem[] = [
    // Ⅰ 対象となる宅地又は建物に関する事項
    { label: "所在・地番", ok: !!p.address, required: true, section: "登記記録" },
    { label: "所有者", ok: !!p.owner_name, required: true, section: "登記記録" },
    { label: "土地面積", ok: !!p.land_area, required: true, section: "登記記録" },
    { label: "建物面積", ok: !!p.building_area, required: true, section: "登記記録" },
    { label: "抵当権", ok: p.mortgage !== undefined && p.mortgage !== "", required: true, section: "登記記録" },
    { label: "用途地域", ok: !!p.zoning, required: true, section: "法令制限" },
    { label: "建ぺい率", ok: !!p.building_coverage_ratio, required: true, section: "法令制限" },
    { label: "容積率", ok: !!p.floor_area_ratio, required: true, section: "法令制限" },
    { label: "防火地域", ok: !!p.fire_zone, required: true, section: "法令制限" },
    { label: "飲用水", ok: !!p.water_supply, required: true, section: "インフラ" },
    { label: "排水", ok: !!p.sewage, required: true, section: "インフラ" },
    { label: "ガス", ok: !!p.gas_type, required: true, section: "インフラ" },
    { label: "電気", ok: !!p.electricity, required: true, section: "インフラ" },
    { label: "接面道路", ok: !!p.road_type, required: true, section: "道路" },
    { label: "道路幅員", ok: !!p.road_width, required: true, section: "道路" },
    { label: "洪水ハザード", ok: !!p.flood_text, required: true, section: "災害" },
    { label: "津波", ok: !!p.tsunami_text, required: true, section: "災害" },
    { label: "高潮", ok: !!p.hightide_text, required: true, section: "災害" },
  ];

  if (isRental) {
    items.push(
      { label: "賃料", ok: !!p.rent, required: true, section: "取引条件" },
      { label: "敷金", ok: !!p.deposit_months, required: true, section: "取引条件" },
      { label: "契約期間", ok: !!p.lease_start && !!p.lease_end, required: true, section: "取引条件" },
      { label: "支払方法", ok: !!p.rent_payment_method, required: true, section: "取引条件" },
    );
  } else {
    items.push(
      { label: "売買代金", ok: !!p.price, required: true, section: "取引条件" },
      { label: "取引態様", ok: !!p.transaction_type, required: true, section: "取引条件" },
    );
  }

  if (isMansion) {
    items.push(
      { label: "管理費", ok: !!p.mgmt_fee, required: true, section: "マンション" },
      { label: "修繕積立金", ok: !!p.repair_reserve, required: true, section: "マンション" },
      { label: "管理形態", ok: !!p.mgmt_form, required: true, section: "マンション" },
    );
  }

  // 任意だが推奨
  items.push(
    { label: "石綿調査", ok: !!p.asbestos, required: false, section: "調査" },
    { label: "耐震診断", ok: !!p.earthquake_resistance, required: false, section: "調査" },
    { label: "告知事項確認", ok: p.is_incident !== undefined, required: false, section: "告知" },
    { label: "特約事項", ok: !!p.special_terms, required: false, section: "特約" },
  );

  const requiredItems = items.filter(i => i.required);
  const okCount = requiredItems.filter(i => i.ok).length;
  const totalRequired = requiredItems.length;
  const allOk = okCount === totalRequired;
  const missingRequired = requiredItems.filter(i => !i.ok);

  return (
    <Section
      icon={ClipboardCheck}
      title="法定記載事項チェック"
      sub={allOk ? "全項目OK" : `必須${totalRequired}項目中 ${totalRequired - okCount}件未入力`}
    >
      {!allOk && (
        <div style={{
          padding: "10px 14px", background: "#FEF2F2", borderRadius: 6,
          border: "1px solid #FECACA", marginBottom: 10, fontSize: 12,
          color: "#991B1B", lineHeight: 1.6,
        }}>
          <strong>宅建業法第35条</strong>に基づく必須記載事項が不足しています：
          <div style={{ marginTop: 6 }}>
            {missingRequired.map((item, i) => (
              <span key={i} style={{
                display: "inline-block", padding: "2px 8px", margin: "2px 4px 2px 0",
                background: "#FEE2E2", borderRadius: 4, fontSize: 11, fontWeight: 600,
              }}>
                {item.section}/{item.label}
              </span>
            ))}
          </div>
        </div>
      )}
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: "none", border: "none", cursor: "pointer",
          fontSize: 12, color: "#2563EB", fontWeight: 600, padding: "4px 0",
        }}
      >
        {open ? "チェックリストを閉じる" : "全項目を確認する"}
      </button>
      {open && (
        <div style={{ marginTop: 8 }}>
          {(() => {
            const sections = [...new Set(items.map(i => i.section))];
            return sections.map(sec => (
              <div key={sec} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "#475569", marginBottom: 4 }}>{sec}</div>
                {items.filter(i => i.section === sec).map((item, i) => (
                  <div key={i} style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "3px 0", fontSize: 12,
                    color: item.ok ? "#166534" : item.required ? "#B91C1C" : "#92400E",
                  }}>
                    <span style={{ fontSize: 14 }}>{item.ok ? "✅" : item.required ? "❌" : "⚠️"}</span>
                    <span style={{ fontWeight: item.ok ? 400 : 600 }}>{item.label}</span>
                    {item.required && !item.ok && <span style={{ fontSize: 9, color: "#DC2626" }}>必須</span>}
                  </div>
                ))}
              </div>
            ));
          })()}
        </div>
      )}
    </Section>
  );
}

/* ─── 操作履歴（監査ログ）─── */
type AuditEntry = { id: number; action: string; details: string; created_at: string; ip_address?: string };

function AuditLogSection({ propertyId }: { propertyId: string }) {
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const loadLogs = useCallback(() => {
    if (loaded) { setOpen(!open); return; }
    fetch(`/api/audit?property_id=${propertyId}&limit=20`)
      .then(r => r.json())
      .then(data => {
        setLogs(data.results || []);
        setLoaded(true);
        setOpen(true);
      })
      .catch(() => setLoaded(true));
  }, [propertyId, loaded, open]);

  const actionLabels: Record<string, { label: string; color: string }> = {
    create: { label: "作成", color: "#166534" },
    update: { label: "更新", color: "#1D4ED8" },
    delete: { label: "削除", color: "#B91C1C" },
    pdf_extract: { label: "PDF抽出", color: "#7C3AED" },
  };

  return (
    <Section icon={Clock} title="操作履歴" sub="電子帳簿保存法対応">
      <button
        onClick={loadLogs}
        style={{
          background: "none", border: "none", cursor: "pointer",
          fontSize: 12, color: "#2563EB", fontWeight: 600, padding: "4px 0",
        }}
      >
        {open ? "閉じる" : "操作履歴を表示"}
      </button>
      {open && (
        <div style={{ marginTop: 8 }}>
          {logs.length === 0 ? (
            <div style={{ fontSize: 12, color: "#94A3B8", padding: "8px 0" }}>
              まだ操作履歴がありません
            </div>
          ) : (
            logs.map(log => {
              const a = actionLabels[log.action] || { label: log.action, color: "#64748B" };
              return (
                <div key={log.id} style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "6px 0", borderBottom: "1px solid #F1F5F9", fontSize: 12,
                }}>
                  <span style={{
                    padding: "1px 6px", borderRadius: 4, fontSize: 10,
                    fontWeight: 700, color: "#fff", background: a.color,
                    flexShrink: 0,
                  }}>
                    {a.label}
                  </span>
                  <span style={{ color: "#334155", flex: 1 }}>{log.details}</span>
                  <span style={{ color: "#94A3B8", fontSize: 10, flexShrink: 0 }}>
                    {new Date(log.created_at + "Z").toLocaleString("ja-JP")}
                  </span>
                </div>
              );
            })
          )}
        </div>
      )}
    </Section>
  );
}

export default function PropertyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [property, setProperty] = useState<PropertyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState("");
  const [fetchError, setFetchError] = useState("");
  const [editMode, setEditMode] = useState(false);
  const [editData, setEditData] = useState<Partial<PropertyData>>({});
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [diffData, setDiffData] = useState<Record<string, { old: string; new: string }> | null>(null);
  const [showPdfExtractor, setShowPdfExtractor] = useState(false);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const loadProperty = useCallback(() => {
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
          setEditData(data);
        }
        setLoading(false);
      })
      .catch(() => {
        setFetchError("読み込みに失敗しました");
        setLoading(false);
      });
  }, [id]);

  useEffect(() => { loadProperty(); }, [loadProperty]);

  const handleSaveEdit = async () => {
    setSaving(true);
    try {
      const res = await fetch(`/api/properties/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editData),
      });
      if (res.ok) {
        const updated = await res.json();
        setProperty(updated);
        setEditMode(false);
        showToast("保存しました");
      } else {
        showToast("保存に失敗しました");
      }
    } catch {
      showToast("ネットワークエラー");
    }
    setSaving(false);
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      const res = await fetch(`/api/properties/${id}`, { method: "DELETE" });
      if (res.ok) {
        showToast("物件を削除しました");
        setTimeout(() => router.push("/dashboard"), 500);
      } else {
        showToast("削除に失敗しました");
        setDeleting(false);
      }
    } catch {
      showToast("ネットワークエラー");
      setDeleting(false);
    }
  };

  const refreshApi = async () => {
    if (!property?.address) return;
    setRefreshing(true);
    setDiffData(null);
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address: property.address }),
      });
      if (res.ok) {
        const apiData: SearchResult = await res.json();

        // Check for differences
        const diffFields: Record<string, { old: string; new: string }> = {};
        const checkDiff = (key: string, oldVal: unknown, newVal: unknown) => {
          const o = oldVal != null ? String(oldVal) : "";
          const n = newVal != null ? String(newVal) : "";
          if (o !== n && (o || n)) {
            diffFields[key] = { old: o || "(なし)", new: n || "(なし)" };
          }
        };
        checkDiff("用途地域", property.zoning, apiData.zoning);
        checkDiff("建ぺい率", property.building_coverage_ratio, apiData.building_coverage_ratio);
        checkDiff("容積率", property.floor_area_ratio, apiData.floor_area_ratio);
        checkDiff("防火地域", property.fire_zone, apiData.fire_zone);
        checkDiff("洪水浸水", property.flood_text, apiData.flood_text);
        checkDiff("津波浸水", property.tsunami_text, apiData.tsunami_text);
        checkDiff("高潮浸水", property.hightide_text, apiData.hightide_text);
        checkDiff("土砂災害", property.landslide_text, apiData.landslide_text);
        checkDiff("公示地価", property.land_price, apiData.land_price);

        if (Object.keys(diffFields).length > 0) {
          setDiffData(diffFields);
        }

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
          setEditData(updated);
          showToast(Object.keys(diffFields).length > 0
            ? `API情報を再取得しました（${Object.keys(diffFields).length}件の変更あり）`
            : "API情報を再取得しました（変更なし）"
          );
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
  const str = (v: unknown) => (v != null && v !== "" ? String(v) : "\u2014");
  const pTypeLabel = p.property_type === "mansion" ? "区分マンション" : p.property_type === "land" ? "土地" : p.property_type === "house" ? "一戸建て" : "一棟";

  const completion = computeCompletionForProperty(p as unknown as Record<string, unknown>);

  const updateEdit = (key: string, val: string) => {
    setEditData((prev) => ({ ...prev, [key]: val }));
  };

  const autoRows: DetailRow[] = [
    { label: "用途地域", value: str(p.zoning), field: "zoning" },
    { label: "建ぺい率", value: p.building_coverage_ratio ? `${p.building_coverage_ratio}%` : "\u2014", field: "building_coverage_ratio" },
    { label: "容積率", value: p.floor_area_ratio ? `${p.floor_area_ratio}%` : "\u2014", field: "floor_area_ratio" },
    { label: "防火地域", value: str(p.fire_zone), field: "fire_zone" },
    { label: "高度地区", value: str(p.height_district), field: "height_district" },
    { label: "都市計画区域", value: str(p.urban_plan_zone), field: "urban_plan_zone" },
  ];

  const hazardRows: DetailRow[] = [
    { label: "洪水浸水想定", value: str(p.flood_text), field: "flood_text" },
    { label: "津波浸水想定", value: str(p.tsunami_text), field: "tsunami_text" },
    { label: "高潮浸水想定", value: str(p.hightide_text), field: "hightide_text" },
    { label: "土砂災害警戒", value: str(p.landslide_text), field: "landslide_text" },
  ];

  const infraRows: DetailRow[] = [
    { label: "上水道", value: str(p.water_supply), field: "water_supply" },
    { label: "下水道", value: str(p.sewage), field: "sewage" },
    { label: "ガス", value: str(p.gas_type), field: "gas_type" },
    { label: "電気", value: str(p.electricity), field: "electricity" },
    { label: "接面道路", value: str(p.road_type), field: "road_type" },
    { label: "道路幅員", value: p.road_width ? `${p.road_width}m` : "\u2014", field: "road_width" },
    { label: "私道負担", value: str(p.private_road), field: "private_road" },
  ];

  const regRows: DetailRow[] = [
    { label: "所有者名", value: str(p.owner_name), field: "owner_name" },
    { label: "土地面積", value: p.land_area ? `${p.land_area}㎡` : "\u2014", field: "land_area" },
    { label: "建物面積", value: p.building_area ? `${p.building_area}㎡` : "\u2014", field: "building_area" },
    { label: "抵当権", value: str(p.mortgage), field: "mortgage" },
  ];

  const contractRows: DetailRow[] = [
    { label: "取引価格", value: p.price ? `${Number(p.price).toLocaleString()}円` : "\u2014", field: "price" },
    { label: "取引態様", value: str(p.transaction_type), field: "transaction_type" },
    { label: "手付金", value: p.earnest_money ? `${Number(p.earnest_money).toLocaleString()}円` : "\u2014", field: "earnest_money" },
    { label: "引渡予定日", value: str(p.delivery_date), field: "delivery_date" },
  ];

  const rentalRows: DetailRow[] = [
    { label: "賃料（月額）", value: p.rent ? `${Number(p.rent).toLocaleString()}円` : "\u2014", field: "rent" },
    { label: "共益費（月額）", value: p.common_area_fee ? `${Number(p.common_area_fee).toLocaleString()}円` : "\u2014", field: "common_area_fee" },
    { label: "敷金", value: p.deposit_months ? `${p.deposit_months}ヶ月` : "\u2014", field: "deposit_months" },
    { label: "礼金", value: p.key_money_months ? `${p.key_money_months}ヶ月` : "\u2014", field: "key_money_months" },
    { label: "契約期間", value: p.lease_term_years ? `${p.lease_term_years}年` : "\u2014", field: "lease_term_years" },
    { label: "契約形態", value: str(p.lease_type), field: "lease_type" },
    { label: "支払方法", value: str(p.rent_payment_method), field: "rent_payment_method" },
    { label: "支払期日", value: str(p.rent_payment_due), field: "rent_payment_due" },
    { label: "更新料", value: str(p.renewal_fee), field: "renewal_fee" },
    { label: "使用目的", value: str(p.purpose_of_use), field: "purpose_of_use" },
    { label: "ペット", value: str(p.pet_allowed), field: "pet_allowed" },
    { label: "喫煙", value: str(p.smoking_allowed), field: "smoking_allowed" },
    { label: "転貸", value: str(p.sublease_allowed), field: "sublease_allowed" },
    { label: "解約予告", value: str(p.cancellation_notice), field: "cancellation_notice" },
    { label: "保証人", value: str(p.guarantor_required), field: "guarantor_required" },
    { label: "保証会社", value: str(p.guarantee_company), field: "guarantee_company" },
    { label: "火災保険", value: str(p.fire_insurance), field: "fire_insurance" },
  ];

  const renderRows = (rows: DetailRow[], isAuto: boolean) => (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
      {rows.map((r) => {
        if (editMode && !isAuto && r.field) {
          return (
            <div key={r.label} style={{ padding: "8px 12px", background: "#FFF7ED", borderRadius: 8, border: "1.5px solid #FDE68A" }}>
              <Field
                label={r.label}
                value={(editData as Record<string, string>)[r.field] || ""}
                onChange={(v) => updateEdit(r.field!, v)}
                half
              />
            </div>
          );
        }
        if (isAuto) {
          return <AutoRow key={r.label} label={r.label} value={r.value} />;
        }
        return (
          <div
            key={r.label}
            style={{
              padding: "12px 16px",
              background: r.value !== "\u2014" ? "#FEF9C3" : "#F8FAFC",
              borderRadius: 8,
              border: `1.5px solid ${r.value !== "\u2014" ? "#FDE047" : "#E2E8F0"}`,
            }}
          >
            <div style={{ fontSize: 11, color: "#64748B", marginBottom: 3, fontWeight: 600 }}>
              {r.label}
              <MissingFieldIndicator value={r.value} label={r.label} />
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, color: r.value !== "\u2014" ? "#854D0E" : "#94A3B8" }}>{r.value}</div>
          </div>
        );
      })}
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
              <span style={{ fontSize: 11, color: "#64748B", fontWeight: 600 }}>
                完了率 {completion.percent}%
              </span>
            </div>
          </div>
          {/* Edit/View toggle */}
          <button
            onClick={() => {
              if (editMode) {
                setEditData(property);
              }
              setEditMode(!editMode);
            }}
            style={{
              display: "flex", alignItems: "center", gap: 6, padding: "8px 14px",
              borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: "pointer",
              border: `1.5px solid ${editMode ? "#2563EB" : "#CBD5E1"}`,
              background: editMode ? "#DBEAFE" : "#FFFFFF",
              color: editMode ? "#2563EB" : "#0F172A",
              transition: "all 0.15s",
            }}
          >
            {editMode ? <><Eye size={14} /> 表示</> : <><Pencil size={14} /> 編集</>}
          </button>
        </div>

        <ProgressBar percent={completion.percent} />

        {/* Diff view */}
        {diffData && (
          <div style={{
            padding: "14px 18px", background: "#FEF3C7", border: "1.5px solid #FDE68A",
            borderRadius: 8, marginBottom: 16,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#854D0E", display: "flex", alignItems: "center", gap: 6 }}>
                <AlertTriangle size={16} /> API再取得で変更があったデータ
              </div>
              <button onClick={() => setDiffData(null)} style={{ background: "none", border: "none", cursor: "pointer", padding: 4 }}>
                <X size={16} color="#854D0E" />
              </button>
            </div>
            {Object.entries(diffData).map(([key, { old: oldVal, new: newVal }]) => (
              <div key={key} style={{ display: "flex", gap: 8, padding: "6px 0", borderBottom: "1px solid #FDE68A", fontSize: 13 }}>
                <span style={{ fontWeight: 700, color: "#854D0E", minWidth: 80 }}>{key}</span>
                <span style={{ color: "#B91C1C", textDecoration: "line-through" }}>{oldVal}</span>
                <span style={{ color: "#64748B" }}>→</span>
                <span style={{ color: "#166534", fontWeight: 600 }}>{newVal}</span>
              </div>
            ))}
          </div>
        )}

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
            {editMode ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {[
                  { label: "管理費（月額）", field: "mgmt_fee" },
                  { label: "修繕積立金（月額）", field: "repair_reserve" },
                  { label: "管理形態", field: "mgmt_form" },
                  { label: "管理会社", field: "mgmt_company" },
                  { label: "総戸数", field: "total_units" },
                  { label: "大規模修繕", field: "major_repair_plan" },
                ].map((item) => (
                  <div key={item.field} style={{ padding: "8px 12px", background: "#FFF7ED", borderRadius: 8, border: "1.5px solid #FDE68A" }}>
                    <Field
                      label={item.label}
                      value={(editData as Record<string, string>)[item.field] || ""}
                      onChange={(v) => updateEdit(item.field, v)}
                      half
                    />
                  </div>
                ))}
              </div>
            ) : (
              renderRows([
                { label: "管理費", value: p.mgmt_fee ? `${Number(p.mgmt_fee).toLocaleString()}円/月` : "\u2014", field: "mgmt_fee" },
                { label: "修繕積立金", value: p.repair_reserve ? `${Number(p.repair_reserve).toLocaleString()}円/月` : "\u2014", field: "repair_reserve" },
                { label: "管理形態", value: str(p.mgmt_form), field: "mgmt_form" },
                { label: "管理会社", value: str(p.mgmt_company), field: "mgmt_company" },
                { label: "総戸数", value: p.total_units ? `${p.total_units}戸` : "\u2014", field: "total_units" },
                { label: "大規模修繕", value: str(p.major_repair_plan), field: "major_repair_plan" },
              ], false)
            )}
          </Section>
        )}

        {(p.is_incident || p.disclosure_notes || p.asbestos || p.earthquake_resistance || editMode) && (
          <Section icon={TriangleAlert} title="告知事項">
            <div style={{ display: "grid", gap: 10 }}>
              {p.is_incident && (
                <div style={{ padding: "12px 16px", background: "#FEE2E2", borderRadius: 8, border: "1.5px solid #FCA5A5" }}>
                  <div style={{ fontSize: 11, color: "#B91C1C", fontWeight: 700, marginBottom: 4 }}>心理的瑕疵あり</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "#B91C1C" }}>{p.incident_detail || "詳細なし"}</div>
                </div>
              )}
              {editMode ? (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  {[
                    { label: "その他告知", field: "disclosure_notes" },
                    { label: "アスベスト", field: "asbestos" },
                    { label: "耐震診断", field: "earthquake_resistance" },
                  ].map((item) => (
                    <div key={item.field} style={{ padding: "8px 12px", background: "#FFF7ED", borderRadius: 8, border: "1.5px solid #FDE68A" }}>
                      <Field
                        label={item.label}
                        value={(editData as Record<string, string>)[item.field] || ""}
                        onChange={(v) => updateEdit(item.field, v)}
                        half
                      />
                    </div>
                  ))}
                </div>
              ) : (
                renderRows([
                  { label: "その他告知", value: str(p.disclosure_notes), field: "disclosure_notes" },
                  { label: "アスベスト", value: str(p.asbestos), field: "asbestos" },
                  { label: "耐震診断", value: str(p.earthquake_resistance), field: "earthquake_resistance" },
                ], false)
              )}
            </div>
          </Section>
        )}

        <Section icon={Scale} title="契約条件（売買）">
          {editMode ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              {[
                { label: "取引価格（円）", field: "price" },
                { label: "取引態様", field: "transaction_type" },
                { label: "手付金（円）", field: "earnest_money" },
                { label: "引渡予定日", field: "delivery_date" },
              ].map((item) => (
                <div key={item.field} style={{ padding: "8px 12px", background: "#FFF7ED", borderRadius: 8, border: "1.5px solid #FDE68A" }}>
                  <Field
                    label={item.label}
                    value={(editData as Record<string, string>)[item.field] || ""}
                    onChange={(v) => updateEdit(item.field, v)}
                    half
                  />
                </div>
              ))}
            </div>
          ) : (
            <>
              {renderRows(contractRows, false)}
              {p.special_terms && (
                <div style={{ marginTop: 10, padding: "12px 16px", background: "#FEF9C3", borderRadius: 8, border: "1.5px solid #FDE047" }}>
                  <div style={{ fontSize: 11, color: "#64748B", fontWeight: 600, marginBottom: 4 }}>特約事項</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "#854D0E", whiteSpace: "pre-wrap" }}>{p.special_terms}</div>
                </div>
              )}
            </>
          )}
        </Section>

        <Section icon={FileText} title="賃貸借条件">
          {editMode ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              {[
                { label: "賃料（月額・円）", field: "rent" },
                { label: "共益費（月額・円）", field: "common_area_fee" },
                { label: "敷金（ヶ月）", field: "deposit_months" },
                { label: "礼金（ヶ月）", field: "key_money_months" },
                { label: "契約期間（年）", field: "lease_term_years" },
                { label: "契約形態", field: "lease_type" },
                { label: "支払方法", field: "rent_payment_method" },
                { label: "支払期日", field: "rent_payment_due" },
                { label: "更新料", field: "renewal_fee" },
                { label: "使用目的", field: "purpose_of_use" },
                { label: "ペット", field: "pet_allowed" },
                { label: "喫煙", field: "smoking_allowed" },
                { label: "転貸", field: "sublease_allowed" },
                { label: "解約予告期間", field: "cancellation_notice" },
                { label: "保証人", field: "guarantor_required" },
                { label: "保証会社", field: "guarantee_company" },
                { label: "火災保険", field: "fire_insurance" },
              ].map((item) => (
                <div key={item.field} style={{ padding: "8px 12px", background: "#EFF6FF", borderRadius: 8, border: "1.5px solid #93C5FD" }}>
                  <Field
                    label={item.label}
                    value={(editData as Record<string, string>)[item.field] || ""}
                    onChange={(v) => updateEdit(item.field, v)}
                    half
                  />
                </div>
              ))}
            </div>
          ) : (
            renderRows(rentalRows, false)
          )}
        </Section>

        {/* Action buttons */}
        {editMode ? (
          <>
          <div style={{ marginBottom: 10 }}>
            <Btn variant="secondary" full icon={Upload} onClick={() => setShowPdfExtractor(true)}>
              PDF / テキストから自動入力
            </Btn>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
            <Btn variant="secondary" full icon={X} onClick={() => { setEditMode(false); setEditData(property); }}>
              キャンセル
            </Btn>
            <Btn variant="success" full icon={FileText} onClick={handleSaveEdit} disabled={saving}>
              {saving ? "保存中..." : "変更を保存"}
            </Btn>
          </div>
          </>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
              <Btn variant="secondary" full icon={RefreshCw} onClick={refreshApi} disabled={refreshing}>
                {refreshing ? "取得中..." : "API再取得"}
              </Btn>
              <Btn variant="success" full icon={Download} onClick={generateCSV}>CSV出力</Btn>
            </div>
            <div style={{ marginBottom: 10 }}>
              <Link href={`/properties/${id}/print`} style={{ textDecoration: "none", display: "block" }}>
                <Btn variant="primary" full icon={Printer}>重説・契約書を出力</Btn>
              </Link>
            </div>
            <div style={{ display: "flex", justifyContent: "center", marginTop: 16 }}>
              {deleteConfirm ? (
                <div style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "12px 18px",
                  background: "#FEE2E2", border: "1.5px solid #FCA5A5", borderRadius: 8,
                }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#B91C1C" }}>本当に削除しますか？</span>
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    style={{
                      padding: "6px 16px", borderRadius: 6, fontSize: 13, fontWeight: 700,
                      background: "#B91C1C", color: "#FFF", border: "none", cursor: deleting ? "default" : "pointer",
                    }}
                  >
                    {deleting ? "削除中..." : "削除する"}
                  </button>
                  <button
                    onClick={() => setDeleteConfirm(false)}
                    style={{
                      padding: "6px 16px", borderRadius: 6, fontSize: 13, fontWeight: 700,
                      background: "#FFF", color: "#0F172A", border: "1.5px solid #CBD5E1", cursor: "pointer",
                    }}
                  >
                    キャンセル
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setDeleteConfirm(true)}
                  style={{
                    display: "flex", alignItems: "center", gap: 6, padding: "8px 16px",
                    borderRadius: 6, fontSize: 12, fontWeight: 600,
                    background: "transparent", color: "#B91C1C", border: "1px solid #FCA5A5",
                    cursor: "pointer", transition: "all 0.15s",
                  }}
                >
                  <Trash2 size={14} /> この物件を削除
                </button>
              )}
            </div>
          </>
        )}

        {/* ── 法定記載事項チェックリスト ── */}
        <LegalChecklist property={p} isRental={!!p.rent} />

        {/* ── 操作履歴（監査ログ）── */}
        <AuditLogSection propertyId={id} />
      </main>

      {showPdfExtractor && property && (
        <PdfExtractor
          currentData={property}
          onApply={(data) => {
            setEditData(prev => ({ ...prev, ...data }));
            setShowPdfExtractor(false);
            showToast(`${Object.keys(data).length}件のデータを反映しました`);
          }}
          onClose={() => setShowPdfExtractor(false)}
        />
      )}

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
