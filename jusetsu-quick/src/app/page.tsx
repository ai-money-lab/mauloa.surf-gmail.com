"use client";

import { useState } from "react";
import { FileText, Mail } from "lucide-react";
import Section from "@/components/ui/Section";
import Field from "@/components/ui/Field";
import Btn from "@/components/ui/Btn";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [licenseNumber, setLicenseNumber] = useState("");
  const [isNew, setIsNew] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = () => {
    // MVP: skip auth, go straight to dashboard
    router.push("/dashboard");
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#F1F5F9",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "40px 18px",
      }}
    >
      <div style={{ textAlign: "center", marginBottom: 32 }}>
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 14,
            background: "#0F172A",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: 16,
          }}
        >
          <FileText size={28} color="#FFF" strokeWidth={2} />
        </div>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0F172A", marginBottom: 4 }}>
          重説クイック
        </h1>
        <p style={{ fontSize: 13, color: "#64748B", fontWeight: 500 }}>
          不動産重要事項説明書 作成支援ツール
        </p>
      </div>

      <div style={{ width: "100%", maxWidth: 420 }}>
        {!sent ? (
          <Section icon={Mail} title="ログイン" sub="メールアドレスでログイン">
            <div style={{ display: "grid", gap: 14 }}>
              <Field
                label="メールアドレス"
                placeholder="example@company.co.jp"
                type="email"
                required
                value={email}
                onChange={setEmail}
              />

              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: 13,
                  fontWeight: 500,
                  color: "#334155",
                  cursor: "pointer",
                }}
                onClick={() => setIsNew(!isNew)}
              >
                <input
                  type="checkbox"
                  checked={isNew}
                  onChange={() => setIsNew(!isNew)}
                  style={{ width: 16, height: 16 }}
                />
                新規登録（会社情報を入力）
              </label>

              {isNew && (
                <>
                  <Field
                    label="会社名"
                    placeholder="例：〇〇不動産株式会社"
                    required
                    value={companyName}
                    onChange={setCompanyName}
                  />
                  <Field
                    label="宅建業免許番号"
                    placeholder="例：東京都知事(3)第12345号"
                    value={licenseNumber}
                    onChange={setLicenseNumber}
                  />
                </>
              )}

              <Btn full onClick={handleSubmit} icon={Mail}>
                ログイン / 利用開始
              </Btn>
            </div>
          </Section>
        ) : (
          <Section icon={Mail} title="メール送信完了">
            <div style={{ textAlign: "center", padding: "20px 0" }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#14532D", marginBottom: 8 }}>
                マジックリンクを送信しました
              </div>
              <div style={{ fontSize: 13, color: "#64748B" }}>
                {email} に届いたリンクをクリックしてログインしてください
              </div>
            </div>
          </Section>
        )}
      </div>

      <div
        style={{
          marginTop: 32,
          fontSize: 10,
          color: "#64748B",
          textAlign: "center",
          lineHeight: 1.7,
          fontWeight: 500,
        }}
      >
        出典：国土交通省 不動産情報ライブラリ / 国土地理院 / ハザードマップAPI（東海大学）
        <br />
        本システムの情報は参考値です。重要事項説明書の作成は宅建士の責任において行ってください。
      </div>
    </div>
  );
}
