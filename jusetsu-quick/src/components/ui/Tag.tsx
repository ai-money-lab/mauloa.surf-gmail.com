"use client";

type TagVariant = "auto" | "manual" | "missing";

const variantMap = {
  auto: { bg: "#DCFCE7", color: "#166534", border: "#86EFAC" },
  manual: { bg: "#FEF9C3", color: "#854D0E", border: "#FDE047" },
  missing: { bg: "#FEE2E2", color: "#B91C1C", border: "#FCA5A5" },
};

export default function Tag({
  variant = "auto",
  children,
}: {
  variant?: TagVariant;
  children: React.ReactNode;
}) {
  const s = variantMap[variant];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        fontSize: 10,
        fontWeight: 700,
        padding: "2px 8px",
        borderRadius: 4,
        background: s.bg,
        color: s.color,
        border: `1px solid ${s.border}`,
        lineHeight: "18px",
        letterSpacing: 0.3,
      }}
    >
      {children}
    </span>
  );
}
