"use client";

import { FileText } from "lucide-react";
import Link from "next/link";

export default function Header() {
  return (
    <header
      style={{
        background: "#0F172A",
        padding: "0 24px",
        height: 52,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <Link href="/dashboard" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 6,
            background: "rgba(255,255,255,0.12)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <FileText size={16} color="#FFF" strokeWidth={2.2} />
        </div>
        <span
          style={{
            color: "#F8FAFC",
            fontSize: 16,
            fontWeight: 700,
            letterSpacing: 1.5,
          }}
        >
          重説クイック
        </span>
      </Link>
    </header>
  );
}
