"use client";

import { useState, useEffect } from "react";
import { Plus, FileText, Clock } from "lucide-react";
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
}

export default function DashboardPage() {
  const [properties, setProperties] = useState<PropertySummary[]>([]);
  const [filter, setFilter] = useState<"all" | "draft" | "completed">("all");

  const [loadError, setLoadError] = useState("");
  const [loaded, setLoaded] = useState(false);

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

  const filtered = properties.filter((p) => {
    if (filter === "all") return true;
    return p.status === filter;
  });

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

        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
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

        {filtered.length === 0 ? (
          <Section icon={FileText} title="物件がありません">
            <div style={{ textAlign: "center", padding: "30px 0" }}>
              <div style={{ fontSize: 14, color: "#64748B", marginBottom: 16, fontWeight: 500 }}>
                まだ物件が登録されていません。
                <br />
                「新規作成」から最初の重説を作成しましょう。
              </div>
              <Link href="/properties/new" style={{ textDecoration: "none" }}>
                <Btn icon={Plus}>新規作成</Btn>
              </Link>
            </div>
          </Section>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {filtered.map((p) => (
              <Link
                key={p.id}
                href={`/properties/${p.id}`}
                style={{ textDecoration: "none" }}
              >
                <div
                  style={{
                    background: "#FFFFFF",
                    border: "1.5px solid #CBD5E1",
                    borderRadius: 10,
                    padding: "14px 18px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    cursor: "pointer",
                    transition: "all 0.15s",
                    boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: "#0F172A", marginBottom: 4 }}>
                      {p.address}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 12, color: "#64748B", fontWeight: 500 }}>
                        {typeLabel(p.property_type)}
                      </span>
                      <Tag variant={p.status === "completed" ? "auto" : "manual"}>
                        {p.status === "completed" ? "完了" : "下書き"}
                      </Tag>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "#64748B" }}>
                    <Clock size={12} />
                    {p.updated_at?.slice(0, 10)}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
