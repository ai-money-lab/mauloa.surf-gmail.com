import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          primary: "#1a3a5c",
          primaryHover: "#244d75",
          accent: "#2563EB",
          accentLight: "#DBEAFE",
        },
        status: {
          success: "#166534",
          successBg: "#DCFCE7",
          successBorder: "#86EFAC",
          successText: "#14532D",
          warning: "#854D0E",
          warningBg: "#FEF9C3",
          warningBorder: "#FDE047",
          danger: "#B91C1C",
          dangerBg: "#FEE2E2",
          dangerBorder: "#FCA5A5",
        },
        ui: {
          bg: "#F1F5F9",
          surface: "#FFFFFF",
          border: "#CBD5E1",
          borderLight: "#E2E8F0",
          text: "#0F172A",
          textSecondary: "#334155",
          textMuted: "#64748B",
          headerBg: "#0F172A",
          tableHead: "#1E293B",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Noto Sans JP",
          "Hiragino Kaku Gothic ProN",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
export default config;
