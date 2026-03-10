"use client";

import Tag from "./Tag";

export default function AutoRow({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div
      style={{
        padding: "12px 16px",
        background: "#DCFCE7",
        borderRadius: 8,
        border: "1.5px solid #86EFAC",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
      }}
    >
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 11, color: "#64748B", marginBottom: 3, fontWeight: 600 }}>
          {label}
        </div>
        <div style={{ fontSize: 16, fontWeight: 700, color: "#14532D" }}>{value}</div>
        {sub && (
          <div style={{ fontSize: 10, color: "#64748B", marginTop: 2 }}>{sub}</div>
        )}
      </div>
      <Tag variant="auto">自動取得</Tag>
    </div>
  );
}
