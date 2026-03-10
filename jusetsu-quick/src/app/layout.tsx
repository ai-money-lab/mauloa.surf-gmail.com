import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "重説クイック",
  description: "不動産重要事項説明書 作成支援ツール",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja">
      <body className="font-sans" style={{ background: "#F1F5F9", color: "#0F172A", minHeight: "100vh" }}>
        {children}
        <footer
          style={{
            padding: "12px 24px",
            textAlign: "center",
            fontSize: 10,
            color: "#64748B",
            borderTop: "1px solid #CBD5E1",
            background: "#FFFFFF",
            lineHeight: 1.7,
            fontWeight: 500,
          }}
        >
          出典：国土交通省 不動産情報ライブラリ / 国土地理院 / ハザードマップAPI（東海大学）
          <br />
          本システムの情報は参考値です。重要事項説明書の作成は宅建士の責任において行ってください。
        </footer>
      </body>
    </html>
  );
}
