"use client";

import { useState, useEffect, useMemo } from "react";
import { Plus, FileText, Clock, Trash2, Search, ArrowUpDown } from "lucide-react";
import Header from "@/components/Header";
import Section from "@/components/ui/Section";
import Btn from "@/components/ui/Btn";
import Tag from "@/components/ui/Tag";
import Link from "next/link";

interface PropertySummary {
  id: string;
  address: string;
  property_type: string;
  status: string;
  created_at: string;
  updated_at: string;
  // completion fields
  zoning?: string;
  building_coverage_ratio?: number;
  floor_area_ratio?: number;
  fire_zone?: string;
  flood_text?: string;
  tsunami_text?: string;
  hightide_text?: string;
  landslide_text?: string;
  land_price?: number;
  water_supply?: string;
  sewage?: string;
  gas_type?: string;
  electricity?: string;
  road_type?: string;
  road_width?: string;
  owner_name?: string;
  land_area?: string;
  mortgage?: string;
  price?: string;
  transaction_type?: string;
  asbestos?: string;
  earthquake_resistance?: string;
  mgmt_fee?: string;
  repair_reserve?: string;
  mgmt_form?: string;
}

function computeCompletion(p: PropertySummary): number {
  const fields: boolean[] = [
    !!p.zoning, !!p.building_coverage_ratio, !!p.floor_area_ratio, !!p.fire_zone,
    !!p.flood_text, !!p.tsunami_text, !!p.hightide_text, !!p.landslide_text, !!p.land_price,
    !!p.water_supply, !!p.sewage, !!p.gas_type, !!p.electricity,
    !!p.road_type, !!p.road_width, !!p.owner_name, !!p.land_area,
    !!p.mortgage, !!p.price, !!p.transaction_type, !!p.asbestos, !!p.earthquake_resistance,
  ];
  if (p.property_type === "mansion" || p.property_type === "condo") {
    fields.push(!!p.mgmt_fee, !!p.repair_reserve, !!p.mgmt_form);
  }
  const filled = fields.filter(Boolean).length;
  const total = fields.length;
  return total > 0 ? Math.round((filled / total) * 100) : 0;
}

type SortKey = "newest" | "oldest" | "address" | "completion";

export default function DashboardPage() {
  const [properties, setProperties] = useState<PropertySummary[]>([]);
  const [filter, setFilter] = useState<"all" | "draft" | "completed">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<SortKey>("newest");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [toast, setToast] = useState("");

  const [loadError, setLoadError] = useState("");
  const [loaded, setLoaded] = useState(false);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  useEffect(() => {
    fetch("/api/properties")
      .then((r) => r.json())
      .then((data) => {
        if (data.results) setProperties(data.results);
        setLoaded(true);
      })
      .catch(() => {
        setLoadError("物件の読み込みに失敗しました");
        setLoaded(true);
      });
  }, []);

  const handleDelete = async (id: string) => {
    setDeleting(true);
    try {
      const res = await fetch(`/api/properties/${id}`, { method: "DELETE" });
      if (res.ok) {
        setProperties((prev) => prev.filter((p) => p.id !== id));
        showToast("物件を削除しました");
      } else {
        showToast("削除に失敗しました");
      }
    } catch {
      showToast("ネットワークエラー");
    }
    setDeleting(false);
    setDeleteConfirm(null);
  };

  const filtered = useMemo(() => {
    let result = properties.filter((p) => {
      if (filter === "all") return true;
      return p.status === filter;
    });

    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      result = result.filter((p) => p.address.toLowerCase().includes(q));
    }

    // Sort
    result = [...result].sort((a, b) => {
      switch (sortBy) {
        case "newest":
          return (b.updated_at || "").localeCompare(a.updated_at || "");
        case "oldest":
          return (a.updated_at || "").localeCompare(b.updated_at || "");
        case "address":
          return a.address.localeCompare(b.address);
        case "completion":
          return computeCompletion(b) - computeCompletion(a);
        default:
          return 0;
      }
    });

    return result;
  }, [properties, filter, searchQuery, sortBy]);

  const typeLabel = (t: string) => {
    const m: Record<string, string> = {
      mansion: "区分マンション",
      land: "土地",
      house: "一戸建て",
      building: "一棟",
      condo: "区分マンション",
    };
    return m[t] || t;
  };

  return (
    <div style={{ minHeight: "100vh", background: "#F1F5F9" }}>
      <Header />

      <main style={{ maxWidth: 740, margin: "0 auto", padding: "22px 18px 100px" }}>
        <div style={{ marginBottom: 18 }}>
          <Link href="/properties/new" style={{ textDecoration: "none", display: "block" }}>
            <Btn full icon={Plus}>新規作成</Btn>
          </Link>
        </div>

        {/* Property count */}
        <div style={{ marginBottom: 12, fontSize: 13, color: "#64748B", fontWeight: 600 }}>
          全 {properties.length} 件の物件
          {filtered.length !== properties.length && ` (${filtered.length} 件を表示中)`}
        </div>

        {/* Search */}
        <div style={{ position: "relative", marginBottom: 12 }}>
          <Search size={16} color="#64748B" style={{ position: "absolute", left: 12, top: 10 }} />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="住所で検索..."
            style={{
              width: "100%",
              padding: "9px 12px 9px 36px",
              borderRadius: 8,
              border: "1.5px solid #CBD5E1",
              fontSize: 14,
              color: "#0F172A",
              outline: "none",
              boxSizing: "border-box",
              fontWeight: 500,
              background: "#FFFFFF",
            }}
          />
        </div>

        {/* Filter + Sort */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 8 }}>
            {(["all", "draft", "completed"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                style={{
                  padding: "8px 16px",
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: filter === f ? 700 : 500,
                  border: `1.5px solid ${filter === f ? "#2563EB" : "#CBD5E1"}`,
                  background: filter === f ? "#DBEAFE" : "#FFFFFF",
                  color: filter === f ? "#2563EB" : "#334155",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                {f === "all" ? "全て" : f === "draft" ? "下書き" : "完了"}
              </button>
            ))}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <ArrowUpDown size={14} color="#64748B" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortKey)}
              style={{
                padding: "6px 10px", borderRadius: 6, fontSize: 12, fontWeight: 600,
                border: "1.5px solid #CBD5E1", background: "#FFFFFF", color: "#334155",
                outline: "none", cursor: "pointer",
              }}
            >
              <option value="newest">新しい順</option>
              <option value="oldest">古い順</option>
              <option value="address">住所順</option>
              <option value="completion">完了率順</option>
            </select>
          </div>
        </div>

        {loadError && (
          <div style={{
            padding: "14px 18px", background: "#FEE2E2", border: "1.5px solid #FCA5A5",
            borderRadius: 8, marginBottom: 16, fontSize: 13, fontWeight: 600, color: "#B91C1C",
          }}>
            {loadError}
          </div>
        )}

        {!loaded ? (
          <div style={{ textAlign: "center", padding: 40, color: "#64748B", fontSize: 14 }}>
            読み込み中...
          </div>
        ) : filtered.length === 0 ? (
          <Section icon={FileText} title="物件がありません">
            <div style={{ textAlign: "center", padding: "30px 0" }}>
              <div style={{ fontSize: 14, color: "#64748B", marginBottom: 16, fontWeight: 500 }}>
                {searchQuery
                  ? `"${searchQuery}" に一致する物件が見つかりません。`
                  : (<>まだ物件が登録されていません。<br />「新規作成」から最初の重説を作成しましょう。</>)}
              </div>
              {!searchQuery && (
                <Link href="/properties/new" style={{ textDecoration: "none" }}>
                  <Btn icon={Plus}>新規作成</Btn>
                </Link>
              )}
            </div>
          </Section>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {filtered.map((p) => {
              const comp = computeCompletion(p);
              const compColor = comp >= 80 ? "#166534" : comp >= 50 ? "#854D0E" : "#B91C1C";
              return (
                <div key={p.id} style={{ position: "relative" }}>
                  <Link
                    href={`/properties/${p.id}`}
                    style={{ textDecoration: "none" }}
                  >
                    <div
                      style={{
                        background: "#FFFFFF",
                        border: "1.5px solid #CBD5E1",
                        borderRadius: 10,
                        padding: "14px 18px",
                        cursor: "pointer",
                        transition: "all 0.15s",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 15, fontWeight: 700, color: "#0F172A", marginBottom: 4 }}>
                            {p.address}
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                            <span style={{ fontSize: 12, color: "#64748B", fontWeight: 500 }}>
                              {typeLabel(p.property_type)}
                            </span>
                            <Tag variant={p.status === "completed" ? "auto" : "manual"}>
                              {p.status === "completed" ? "完了" : "下書き"}
                            </Tag>
                            <span style={{ fontSize: 11, fontWeight: 700, color: compColor }}>
                              {comp}%
                            </span>
                          </div>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "#64748B" }}>
                            <Clock size={12} />
                            {p.updated_at?.slice(0, 10)}
                          </div>
                        </div>
                      </div>
                      {/* Mini progress bar */}
                      <div style={{ marginTop: 8, background: "#E2E8F0", borderRadius: 3, height: 4, overflow: "hidden" }}>
                        <div style={{ height: "100%", background: compColor, borderRadius: 3, width: `${comp}%`, transition: "width 0.3s" }} />
                      </div>
                    </div>
                  </Link>
                  {/* Delete button */}
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      setDeleteConfirm(p.id);
                    }}
                    style={{
                      position: "absolute", top: 14, right: -6, transform: "translateX(100%)",
                      background: "transparent", border: "none", cursor: "pointer", padding: 6,
                      borderRadius: 6, display: "flex", alignItems: "center",
                    }}
                    title="削除"
                  >
                    <Trash2 size={14} color="#CBD5E1" />
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Delete confirmation modal */}
        {deleteConfirm && (
          <div style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
          }}>
            <div style={{
              background: "#FFFFFF", borderRadius: 12, padding: "24px 28px",
              boxShadow: "0 8px 30px rgba(0,0,0,0.2)", maxWidth: 360, width: "90%",
            }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: "#0F172A", marginBottom: 8 }}>
                物件を削除
              </div>
              <div style={{ fontSize: 13, color: "#64748B", marginBottom: 20, fontWeight: 500 }}>
                この物件を削除すると元に戻せません。よろしいですか？
              </div>
              <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                <button
                  onClick={() => setDeleteConfirm(null)}
                  style={{
                    padding: "8px 18px", borderRadius: 6, fontSize: 13, fontWeight: 700,
                    background: "#FFFFFF", color: "#0F172A", border: "1.5px solid #CBD5E1",
                    cursor: "pointer",
                  }}
                >
                  キャンセル
                </button>
                <button
                  onClick={() => handleDelete(deleteConfirm)}
                  disabled={deleting}
                  style={{
                    padding: "8px 18px", borderRadius: 6, fontSize: 13, fontWeight: 700,
                    background: "#B91C1C", color: "#FFF", border: "none",
                    cursor: deleting ? "default" : "pointer",
                  }}
                >
                  {deleting ? "削除中..." : "削除する"}
                </button>
              </div>
            </div>
          </div>
        )}
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
