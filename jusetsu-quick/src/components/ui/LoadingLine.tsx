"use client";

import { CheckCircle2, Loader2 } from "lucide-react";

export default function LoadingLine({
  label,
  done,
  active,
}: {
  label: string;
  done: boolean;
  active: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "6px 0",
        color: done ? "#166534" : active ? "#0F172A" : "#64748B",
        fontSize: 13,
        fontWeight: done || active ? 600 : 400,
      }}
    >
      {done ? (
        <CheckCircle2 size={16} color="#166534" strokeWidth={2.5} />
      ) : active ? (
        <Loader2
          size={16}
          color="#2563EB"
          strokeWidth={2.5}
          className="animate-spin-slow"
        />
      ) : (
        <div
          style={{
            width: 16,
            height: 16,
            borderRadius: "50%",
            border: "2px solid #CBD5E1",
          }}
        />
      )}
      {label}
    </div>
  );
}
