"use client";

import { useState, useCallback, useRef } from "react";
import type { PropertyData } from "@/lib/types";

/* ─── フィールド表示名マップ ─── */
const FIELD_LABELS: Record<string, string> = {
  address: "所在地", owner_name: "所有者", land_area: "土地面積(㎡)",
  building_area: "建物面積(㎡)", property_type: "物件種別", mortgage: "抵当権",
  zoning: "用途地域", building_coverage_ratio: "建ぺい率(%)",
  floor_area_ratio: "容積率(%)", fire_zone: "防火地域",
  road_type: "接面道路", road_width: "道路幅員(m)",
  water_supply: "飲用水", sewage: "排水", gas_type: "ガス", electricity: "電気",
  price: "売買代金(円)", rent: "賃料月額(円)", common_area_fee: "共益費(円)",
  deposit_months: "敷金(月)", key_money_months: "礼金(月)",
  mgmt_fee: "管理費(円)", repair_reserve: "修繕積立金(円)",
  total_units: "総戸数", mgmt_form: "管理形態", mgmt_company: "管理会社",
  lease_start: "契約開始日", lease_end: "契約終了日", lease_type: "契約種類",
  transaction_type: "取引態様", earnest_money: "手付金(円)",
  delivery_date: "引渡予定日", special_terms: "特約事項",
};

const PROPERTY_TYPE_LABELS: Record<string, string> = {
  mansion: "区分マンション", house: "一戸建て", land: "土地", building: "一棟",
};

type ExtractResult = {
  extracted: Record<string, unknown>;
  document_type: string;
  field_count: number;
};

interface Props {
  currentData: PropertyData;
  onApply: (data: Partial<PropertyData>) => void;
  onClose: () => void;
}

export default function PdfExtractor({ currentData, onApply, onClose }: Props) {
  const [step, setStep] = useState<"upload" | "extracting" | "review">("upload");
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [pasteText, setPasteText] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  /* PDF テキスト抽出（pdfjs-dist） */
  const extractTextFromPdf = useCallback(async (file: File): Promise<string> => {
    const pdfjsLib = await import("pdfjs-dist");
    pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;

    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    const pages: string[] = [];
    for (let i = 1; i <= Math.min(pdf.numPages, 10); i++) {
      const page = await pdf.getPage(i);
      const content = await page.getTextContent();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      pages.push(content.items.map((item: any) => item.str).join(" "));
    }
    return pages.join("\n\n");
  }, []);

  /* 抽出実行 */
  const runExtraction = useCallback(async (text: string) => {
    setStep("extracting");
    setError("");
    try {
      const res = await fetch("/api/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "抽出に失敗しました");
        setStep("upload");
        return;
      }
      setResult(data);
      // デフォルトで全フィールドを選択（既存値がある場合はオフ）
      const sel: Record<string, boolean> = {};
      for (const key of Object.keys(data.extracted)) {
        const existing = (currentData as unknown as Record<string, unknown>)[key];
        sel[key] = !existing || existing === "" || existing === 0;
      }
      setSelected(sel);
      setStep("review");
    } catch (e) {
      setError(e instanceof Error ? e.message : "通信エラー");
      setStep("upload");
    }
  }, [currentData]);

  /* ファイル処理 */
  const handleFile = useCallback(async (file: File) => {
    setError("");
    if (file.type === "application/pdf") {
      try {
        const text = await extractTextFromPdf(file);
        if (text.trim().length < 20) {
          setError("PDFからテキストを抽出できませんでした（画像PDFの可能性があります）");
          return;
        }
        await runExtraction(text);
      } catch {
        setError("PDFの読み取りに失敗しました");
      }
    } else if (file.type === "text/plain" || file.name.endsWith(".txt")) {
      const text = await file.text();
      await runExtraction(text);
    } else {
      setError("PDFまたはテキストファイルをアップロードしてください");
    }
  }, [extractTextFromPdf, runExtraction]);

  /* ドラッグ&ドロップ */
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  /* 適用 */
  const applySelected = useCallback(() => {
    if (!result) return;
    const data: Partial<PropertyData> = {};
    for (const [key, val] of Object.entries(result.extracted)) {
      if (selected[key] && val != null && val !== "") {
        (data as Record<string, unknown>)[key] = val;
      }
    }
    onApply(data);
  }, [result, selected, onApply]);

  const allSelected = result ? Object.keys(result.extracted).every(k => selected[k]) : false;
  const toggleAll = () => {
    if (!result) return;
    const next = !allSelected;
    const sel: Record<string, boolean> = {};
    for (const k of Object.keys(result.extracted)) sel[k] = next;
    setSelected(sel);
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,.5)", zIndex: 2000,
      display: "flex", alignItems: "center", justifyContent: "center",
    }} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={{
        background: "#fff", borderRadius: 12, width: "min(600px, 90vw)",
        maxHeight: "85vh", overflow: "auto", boxShadow: "0 8px 30px rgba(0,0,0,.2)",
      }}>
        {/* ヘッダー */}
        <div style={{
          padding: "16px 20px", borderBottom: "1px solid #E2E8F0",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#0F172A" }}>
              PDF / テキストから自動入力
            </div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>
              登記簿謄本・マイソク・契約書などからデータを自動抽出
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "none", border: "none", fontSize: 20, cursor: "pointer",
            color: "#94A3B8", padding: "4px 8px",
          }}>&#x2715;</button>
        </div>

        <div style={{ padding: 20 }}>
          {/* ─── アップロード画面 ─── */}
          {step === "upload" && (
            <>
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
                onClick={() => fileRef.current?.click()}
                style={{
                  border: `2px dashed ${dragOver ? "#2563EB" : "#CBD5E1"}`,
                  borderRadius: 10, padding: "30px 20px", textAlign: "center",
                  cursor: "pointer", transition: "all .2s",
                  background: dragOver ? "#EFF6FF" : "#F8FAFC",
                }}
              >
                <div style={{ fontSize: 32, marginBottom: 8 }}>📄</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#334155" }}>
                  PDFファイルをドラッグ&ドロップ
                </div>
                <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 4 }}>
                  またはクリックしてファイルを選択
                </div>
                <div style={{ fontSize: 10, color: "#94A3B8", marginTop: 8 }}>
                  対応: 登記簿謄本 / マイソク / 賃貸契約書 / 重要事項説明書 / その他
                </div>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.txt"
                  style={{ display: "none" }}
                  onChange={(e) => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }}
                />
              </div>

              <div style={{ margin: "16px 0 8px", display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ flex: 1, height: 1, background: "#E2E8F0" }} />
                <span style={{ fontSize: 11, color: "#94A3B8" }}>または テキストを貼り付け</span>
                <div style={{ flex: 1, height: 1, background: "#E2E8F0" }} />
              </div>

              <textarea
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                placeholder="登記簿の内容やマイソクのテキストをここに貼り付け..."
                style={{
                  width: "100%", minHeight: 100, border: "1px solid #CBD5E1",
                  borderRadius: 8, padding: 12, fontSize: 12, resize: "vertical",
                  fontFamily: "monospace",
                }}
              />
              {pasteText.trim().length > 10 && (
                <button
                  onClick={() => runExtraction(pasteText)}
                  style={{
                    marginTop: 8, width: "100%", padding: "10px",
                    background: "#2563EB", color: "#fff", border: "none",
                    borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: "pointer",
                  }}
                >
                  テキストからデータを抽出
                </button>
              )}

              {error && (
                <div style={{
                  marginTop: 12, padding: "10px 14px", borderRadius: 8,
                  background: "#FEF2F2", color: "#DC2626", fontSize: 12,
                  border: "1px solid #FECACA",
                }}>
                  {error}
                </div>
              )}
            </>
          )}

          {/* ─── 抽出中 ─── */}
          {step === "extracting" && (
            <div style={{ textAlign: "center", padding: "40px 20px" }}>
              <div style={{ fontSize: 28, marginBottom: 12, animation: "spin 1.5s linear infinite" }}>
                &#9881;
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#334155" }}>
                AIがデータを抽出中...
              </div>
              <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 4 }}>
                登記情報・物件概要・契約条件を解析しています
              </div>
              <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
            </div>
          )}

          {/* ─── レビュー画面 ─── */}
          {step === "review" && result && (
            <>
              {/* 書類種別バッジ */}
              <div style={{
                display: "flex", alignItems: "center", gap: 8,
                marginBottom: 12, flexWrap: "wrap",
              }}>
                <span style={{
                  padding: "3px 10px", borderRadius: 20, fontSize: 11,
                  fontWeight: 700, background: "#DBEAFE", color: "#1D4ED8",
                }}>
                  {result.document_type}
                </span>
                <span style={{ fontSize: 11, color: "#64748B" }}>
                  {result.field_count}件のデータを抽出
                </span>
                <div style={{ flex: 1 }} />
                <button onClick={toggleAll} style={{
                  fontSize: 10, color: "#2563EB", background: "none",
                  border: "none", cursor: "pointer", textDecoration: "underline",
                }}>
                  {allSelected ? "すべて解除" : "すべて選択"}
                </button>
              </div>

              {/* 抽出結果テーブル */}
              <div style={{
                border: "1px solid #E2E8F0", borderRadius: 8, overflow: "hidden",
              }}>
                <table style={{
                  width: "100%", borderCollapse: "collapse", fontSize: 12,
                }}>
                  <thead>
                    <tr style={{ background: "#F1F5F9" }}>
                      <th style={{ padding: "6px 10px", textAlign: "left", width: 30 }}></th>
                      <th style={{ padding: "6px 10px", textAlign: "left", fontSize: 11 }}>項目</th>
                      <th style={{ padding: "6px 10px", textAlign: "left", fontSize: 11 }}>抽出値</th>
                      <th style={{ padding: "6px 10px", textAlign: "left", fontSize: 11 }}>現在の値</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(result.extracted).map(([key, val]) => {
                      const current = (currentData as unknown as Record<string, unknown>)[key];
                      const hasConflict = current && current !== "" && current !== 0 && String(current) !== String(val);
                      return (
                        <tr
                          key={key}
                          style={{
                            borderTop: "1px solid #E2E8F0",
                            background: hasConflict ? "#FFFBEB" : selected[key] ? "#F0FDF4" : undefined,
                          }}
                        >
                          <td style={{ padding: "6px 10px", textAlign: "center" }}>
                            <input
                              type="checkbox"
                              checked={!!selected[key]}
                              onChange={() => setSelected(prev => ({ ...prev, [key]: !prev[key] }))}
                            />
                          </td>
                          <td style={{
                            padding: "6px 10px", fontWeight: 600, color: "#334155",
                            whiteSpace: "nowrap", fontSize: 11,
                          }}>
                            {FIELD_LABELS[key] || key}
                          </td>
                          <td style={{ padding: "6px 10px", color: "#059669", fontWeight: 600 }}>
                            {key === "property_type"
                              ? PROPERTY_TYPE_LABELS[String(val)] || String(val)
                              : typeof val === "number" ? val.toLocaleString() : String(val)
                            }
                          </td>
                          <td style={{ padding: "6px 10px", color: "#94A3B8", fontSize: 11 }}>
                            {(current != null && current !== "" && current !== 0)
                              ? (key === "property_type"
                                  ? PROPERTY_TYPE_LABELS[String(current)] || String(current)
                                  : typeof current === "number" ? current.toLocaleString() : String(current))
                              : <span style={{ color: "#CBD5E1" }}>-</span>
                            }
                            {hasConflict ? (
                              <span style={{
                                marginLeft: 6, fontSize: 9, color: "#D97706",
                                fontWeight: 700,
                              }}>上書き</span>
                            ) : null}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* アクションボタン */}
              <div style={{
                display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end",
              }}>
                <button onClick={() => { setStep("upload"); setResult(null); setPasteText(""); }}
                  style={{
                    padding: "8px 16px", borderRadius: 8, border: "1px solid #CBD5E1",
                    background: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer",
                  }}
                >
                  別のファイルを読む
                </button>
                <button
                  onClick={applySelected}
                  disabled={!Object.values(selected).some(Boolean)}
                  style={{
                    padding: "8px 20px", borderRadius: 8, border: "none",
                    background: Object.values(selected).some(Boolean) ? "#2563EB" : "#94A3B8",
                    color: "#fff", fontSize: 12, fontWeight: 700, cursor: "pointer",
                  }}
                >
                  選択した{Object.values(selected).filter(Boolean).length}件を反映
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
