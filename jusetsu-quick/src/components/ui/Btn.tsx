"use client";

import type { LucideIcon } from "lucide-react";

type BtnVariant = "primary" | "secondary" | "success";

const styles: Record<BtnVariant, { bg: string; color: string; border: string }> = {
  primary: { bg: "#1a3a5c", color: "#FFF", border: "#1a3a5c" },
  secondary: { bg: "#FFFFFF", color: "#0F172A", border: "#CBD5E1" },
  success: { bg: "#15803D", color: "#FFF", border: "#15803D" },
};

export default function Btn({
  children,
  variant = "primary",
  onClick,
  disabled,
  full,
  icon: Icon,
  type,
}: {
  children: React.ReactNode;
  variant?: BtnVariant;
  onClick?: () => void;
  disabled?: boolean;
  full?: boolean;
  icon?: LucideIcon;
  type?: "button" | "submit";
}) {
  const s = styles[variant];
  return (
    <button
      type={type || "button"}
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        padding: "12px 22px",
        borderRadius: 8,
        fontSize: 14,
        fontWeight: 700,
        background: disabled ? "#E2E8F0" : s.bg,
        color: disabled ? "#64748B" : s.color,
        border: `1.5px solid ${disabled ? "#E2E8F0" : s.border}`,
        cursor: disabled ? "default" : "pointer",
        width: full ? "100%" : undefined,
        boxShadow: disabled
          ? "none"
          : variant === "primary"
            ? "0 2px 6px rgba(26,58,92,0.25)"
            : variant === "success"
              ? "0 2px 6px rgba(21,128,61,0.25)"
              : "none",
        transition: "all 0.15s",
        letterSpacing: 0.3,
      }}
    >
      {Icon && <Icon size={15} strokeWidth={2.5} />}
      {children}
    </button>
  );
}
