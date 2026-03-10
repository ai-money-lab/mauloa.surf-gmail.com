"use client";

import type { LucideIcon } from "lucide-react";

export default function Section({
  icon: Icon,
  title,
  sub,
  children,
}: {
  icon: LucideIcon;
  title: string;
  sub?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        background: "#FFFFFF",
        border: "1px solid #CBD5E1",
        borderRadius: 10,
        marginBottom: 14,
        overflow: "hidden",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
      }}
    >
      <div
        style={{
          padding: "14px 18px",
          borderBottom: "1.5px solid #E2E8F0",
          display: "flex",
          alignItems: "center",
          gap: 10,
          background: "#F8FAFC",
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: "#1a3a5c",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Icon size={16} color="#FFF" strokeWidth={2.2} />
        </div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#0F172A" }}>{title}</div>
          {sub && (
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 1 }}>{sub}</div>
          )}
        </div>
      </div>
      <div style={{ padding: 18 }}>{children}</div>
    </div>
  );
}
