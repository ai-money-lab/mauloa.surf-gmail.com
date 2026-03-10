"use client";

import { ChevronRight, Check } from "lucide-react";

const STEPS = [
  { id: 1, label: "住所入力" },
  { id: 2, label: "取得結果" },
  { id: 3, label: "インフラ・登記" },
  { id: 4, label: "告知・契約" },
  { id: 5, label: "確認・出力" },
];

export default function StepNav({
  current,
  onGo,
  canNavigate,
}: {
  current: number;
  onGo: (step: number) => void;
  canNavigate: boolean;
}) {
  return (
    <nav
      style={{
        background: "#FFFFFF",
        borderBottom: "2px solid #E2E8F0",
        padding: "0 24px",
        display: "flex",
        alignItems: "stretch",
        height: 46,
        boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
        overflowX: "auto",
      }}
    >
      {STEPS.map((s, i) => {
        const active = current === s.id;
        const done = s.id < current;
        const clickable = canNavigate || s.id === 1;
        return (
          <div
            key={s.id}
            onClick={() => clickable && onGo(s.id)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
              padding: "0 16px",
              cursor: clickable ? "pointer" : "default",
              borderBottom: active ? "3px solid #2563EB" : "3px solid transparent",
              marginBottom: -2,
              color: active ? "#2563EB" : done ? "#166534" : "#64748B",
              fontSize: 13,
              fontWeight: active || done ? 700 : 500,
              transition: "all 0.15s",
              whiteSpace: "nowrap",
            }}
          >
            <span
              style={{
                width: 22,
                height: 22,
                borderRadius: "50%",
                fontSize: 11,
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                background: active ? "#2563EB" : done ? "#166534" : "#E2E8F0",
                color: active || done ? "#FFF" : "#64748B",
              }}
            >
              {done ? <Check size={12} strokeWidth={3} /> : s.id}
            </span>
            <span>{s.label}</span>
            {i < STEPS.length - 1 && (
              <ChevronRight size={14} color="#CBD5E1" style={{ marginLeft: 6 }} />
            )}
          </div>
        );
      })}
    </nav>
  );
}
