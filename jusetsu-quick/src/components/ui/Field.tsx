"use client";

export default function Field({
  label,
  placeholder,
  type = "text",
  required,
  options,
  half,
  value,
  onChange,
}: {
  label: string;
  placeholder?: string;
  type?: string;
  required?: boolean;
  options?: string[];
  half?: boolean;
  value?: string;
  onChange?: (val: string) => void;
}) {
  return (
    <div style={{ gridColumn: half ? undefined : "1 / -1" }}>
      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 12,
          fontWeight: 600,
          color: "#0F172A",
          marginBottom: 6,
        }}
      >
        {label}
        {required && (
          <span
            style={{
              color: "#FFF",
              fontSize: 9,
              fontWeight: 700,
              background: "#B91C1C",
              padding: "1px 5px",
              borderRadius: 3,
            }}
          >
            必須
          </span>
        )}
      </label>
      {options ? (
        <select
          value={value || ""}
          onChange={(e) => onChange?.(e.target.value)}
          style={{
            width: "100%",
            padding: "10px 12px",
            borderRadius: 6,
            fontSize: 14,
            border: "1.5px solid #CBD5E1",
            color: "#0F172A",
            background: "#FFFFFF",
            outline: "none",
            fontWeight: 500,
          }}
        >
          <option value="">選択してください</option>
          {options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      ) : type === "textarea" ? (
        <textarea
          placeholder={placeholder}
          rows={3}
          value={value || ""}
          onChange={(e) => onChange?.(e.target.value)}
          style={{
            width: "100%",
            padding: "10px 12px",
            borderRadius: 6,
            fontSize: 14,
            border: "1.5px solid #CBD5E1",
            color: "#0F172A",
            outline: "none",
            resize: "vertical",
            fontFamily: "inherit",
            boxSizing: "border-box",
          }}
        />
      ) : (
        <input
          type={type}
          placeholder={placeholder}
          value={value || ""}
          onChange={(e) => onChange?.(e.target.value)}
          style={{
            width: "100%",
            padding: "10px 12px",
            borderRadius: 6,
            fontSize: 14,
            border: "1.5px solid #CBD5E1",
            color: "#0F172A",
            outline: "none",
            boxSizing: "border-box",
          }}
        />
      )}
    </div>
  );
}
