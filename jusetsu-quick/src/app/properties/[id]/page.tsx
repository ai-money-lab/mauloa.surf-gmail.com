"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Header from "@/components/Header";
import Section from "@/components/ui/Section";
import AutoRow from "@/components/ui/AutoRow";
import Btn from "@/components/ui/Btn";
import Tag from "@/components/ui/Tag";
import { FileText, ChevronLeft, Download, RefreshCw } from "lucide-react";
import Link from "next/link";
import { floodLevelToText } from "@/lib/api/hazard";

export default function PropertyDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [property, setProperty] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/properties/${id}`)
      .then((r) => r.json())
      .then((data) => {
        setProperty(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "#F1F5F9" }}>
        <Header />
        <main style={{ maxWidth: 740, margin: "0 auto", padding: "22px 18px" }}>
          <div style={{ textAlign: "center", padding: 60, color: "#64748B" }}>読み込み中...</div>
        </main>
      </div>
    );
  }

  if (!property) {
    return (
      <div style={{ minHeight: "100vh", background: "#F1F5F9" }}>
        <Header />
        <main style={{ maxWidth: 740, margin: "0 auto", padding: "22px 18px" }}>
          <Section icon={FileText} title="物件が見つかりません">
            <div style={{ textAlign: "center", padding: 30 }}>
              <Link href="/dashboard"><Btn icon={ChevronLeft}>ダッシュボードに戻る</Btn></Link>
            </div>
          </Section>
        </main>
      </div>
    );
  }

  const p = property;
  const str = (v: unknown) => (v != null ? String(v) : "—");

  return (
    <div style={{ minHeight: "100vh", background: "#F1F5F9" }}>
      <Header />
      <main style={{ maxWidth: 740, margin: "0 auto", padding: "22px 18px 100px" }}>
        <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 10 }}>
          <Link href="/dashboard" style={{ textDecoration: "none" }}>
            <Btn variant="secondary" icon={ChevronLeft}>戻る</Btn>
          </Link>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#0F172A" }}>{str(p.address)}</div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 4 }}>
              <Tag variant={p.status === "completed" ? "auto" : "manual"}>
                {p.status === "completed" ? "完了" : "下書き"}
              </Tag>
              <span style={{ fontSize: 12, color: "#64748B" }}>
                更新: {str(p.updated_at).slice(0, 10)}
              </span>
            </div>
          </div>
        </div>

        <Section icon={FileText} title="都市計画・ハザード情報">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <AutoRow label="用途地域" value={str(p.zoning)} />
            <AutoRow label="防火地域" value={str(p.fire_zone)} />
            <AutoRow label="建ぺい率" value={p.building_coverage_ratio ? `${p.building_coverage_ratio}%` : "—"} />
            <AutoRow label="容積率" value={p.floor_area_ratio ? `${p.floor_area_ratio}%` : "—"} />
            <AutoRow label="洪水浸水想定" value={floodLevelToText(Number(p.flood_level) || 0)} />
            <AutoRow label="学区" value={str(p.school_district)} />
          </div>
        </Section>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <Btn variant="secondary" full icon={RefreshCw}>API再取得</Btn>
          <Btn variant="success" full icon={Download}>CSV出力</Btn>
        </div>
      </main>
    </div>
  );
}
