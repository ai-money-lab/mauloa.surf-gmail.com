"use client";

import { useState, useCallback, useRef } from "react";
import type { PropertyData } from "@/lib/types";

/* ─── pdfjs worker URL（CDNフォールバック付き） ─── */
function getPdfjsWorkerSrc(version: string): string {
  return `//cdn.jsdelivr.net/npm/pdfjs-dist@${version}/build/pdf.worker.min.mjs`;
}

/* ─── OCR: Tesseract.js（画像PDFフォールバック用） ─── */
async function ocrFromPdfPages(file: File, onProgress?: (msg: string) => void): Promise<string> {
  const pdfjsLib = await import("pdfjs-dist");
  if (!pdfjsLib.GlobalWorkerOptions.workerSrc) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = getPdfjsWorkerSrc(pdfjsLib.version);
  }
  const { createWorker } = await import("tesseract.js");

  const arrayBuffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: new Uint8Array(arrayBuffer) }).promise;
  const pageCount = Math.min(pdf.numPages, 10);

  onProgress?.(`OCRエンジン起動中...`);
  const worker = await createWorker("jpn+eng");

  const pages: string[] = [];
  try {
    for (let i = 1; i <= pageCount; i++) {
      onProgress?.(`ページ ${i}/${pageCount} をOCR処理中...`);
      const page = await pdf.getPage(i);
      const viewport = page.getViewport({ scale: 2.0 });

      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      const ctx = canvas.getContext("2d")!;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      await page.render({ canvasContext: ctx, viewport, canvas } as any).promise;

      const { data } = await worker.recognize(canvas);
      if (data.text.trim()) {
        pages.push(data.text);
      }
    }
  } finally {
    await worker.terminate();
  }

  return pages.join("\n\n");
}

/* ─── OCR: 画像ファイル（JPEG/PNG/WEBP）直接認識 ─── */
async function ocrFromImage(file: File, onProgress?: (msg: string) => void): Promise<string> {
  const { createWorker } = await import("tesseract.js");

  onProgress?.("OCRエンジン起動中...");
  const worker = await createWorker("jpn+eng");

  try {
    onProgress?.("画像を文字認識中...");
    const { data } = await worker.recognize(file);
    return data.text;
  } finally {
    await worker.terminate();
  }
}

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
  const [step, setStep] = useState<"upload" | "ocr" | "extracting" | "review">("upload");
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [pasteText, setPasteText] = useState("");
  const [ocrProgress, setOcrProgress] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  /* PDF テキスト抽出（pdfjs-dist） */
  const extractTextFromPdf = useCallback(async (file: File): Promise<string> => {
    const pdfjsLib = await import("pdfjs-dist");
    if (!pdfjsLib.GlobalWorkerOptions.workerSrc) {
      pdfjsLib.GlobalWorkerOptions.workerSrc = getPdfjsWorkerSrc(pdfjsLib.version);
    }

    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: new Uint8Array(arrayBuffer) }).promise;
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
      const data = await res.json().catch(() => ({ error: `サーバーエラー (HTTP ${res.status})` }));
      if (!res.ok) {
        setError(data.error || `抽出に失敗しました (HTTP ${res.status})`);
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

  /* ファイル判定 */
  const isPdf = (file: File) =>
    file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  const isText = (file: File) =>
    file.type === "text/plain" || file.name.toLowerCase().endsWith(".txt");
  const isImage = (file: File) => {
    const ext = file.name.toLowerCase();
    return file.type.startsWith("image/") ||
      [".jpg", ".jpeg", ".png", ".webp"].some(e => ext.endsWith(e));
  };

  /* ファイル処理 */
  const handleFile = useCallback(async (file: File) => {
    console.log("[PDF] handleFile called:", file.name, file.type, file.size);
    setError("");

    if (isImage(file)) {
      // 画像ファイル → 直接OCR
      setStep("ocr");
      setOcrProgress("画像を文字認識中...");
      try {
        const ocrText = await ocrFromImage(file, setOcrProgress);
        console.log("[IMG] OCR完了:", ocrText.length, "文字");
        if (ocrText.trim().length < 10) {
          setError("画像から文字を認識できませんでした。鮮明な画像をお試しください。");
          setStep("upload");
          return;
        }
        await runExtraction(ocrText);
      } catch (e) {
        console.error("[IMG] OCRエラー:", e);
        setError(`画像OCRに失敗しました: ${e instanceof Error ? e.message : "不明なエラー"}`);
        setStep("upload");
      }
    } else if (isPdf(file)) {
      try {
        // まずテキスト抽出を試行
        let text = "";
        try {
          text = await extractTextFromPdf(file);
          console.log("[PDF] テキスト抽出完了:", text.length, "文字");
        } catch (e) {
          console.error("[PDF] テキスト抽出エラー:", e);
        }
        if (text.trim().length >= 20) {
          await runExtraction(text);
          return;
        }
        // テキストが少ない → 画像PDF → OCRフォールバック
        console.log("[PDF] テキスト少量 → OCRフォールバック");
        setStep("ocr");
        setOcrProgress("OCR処理を開始します...");
        try {
          const ocrText = await ocrFromPdfPages(file, setOcrProgress);
          console.log("[PDF] OCR完了:", ocrText.length, "文字");
          if (ocrText.trim().length < 20) {
            setError("OCRでも文字を認識できませんでした。画質の良いPDFをお試しください。");
            setStep("upload");
            return;
          }
          await runExtraction(ocrText);
        } catch (e) {
          console.error("[PDF] OCRエラー:", e);
          setError(`OCR処理に失敗しました: ${e instanceof Error ? e.message : "不明なエラー"}`);
          setStep("upload");
        }
      } catch (e) {
        console.error("[PDF] 処理エラー:", e);
        setError(`PDFの読み取りに失敗しました: ${e instanceof Error ? e.message : "不明なエラー"}`);
        setStep("upload");
      }
    } else if (isText(file)) {
      const text = await file.text();
      await runExtraction(text);
    } else {
      setError(`対応していないファイル形式です (${file.type || file.name})`);
    }
  }, [extractTextFromPdf, runExtraction]);

  /* ドラッグ&ドロップ */
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    console.log("[PDF] onDrop fired, files:", e.dataTransfer.files.length);
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
              書類から自動入力
            </div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>
              PDF・画像・テキストからデータを自動抽出（OCR対応）
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "none", border: "none", fontSize: 20, cursor: "pointer",
            color: "#94A3B8", padding: "4px 8px",
          }}>&#x2715;</button>
        </div>

        {/* セキュリティ＆免責バナー */}
        <div style={{
          padding: "8px 20px", background: "#F0FDF4", borderBottom: "1px solid #BBF7D0",
          display: "flex", alignItems: "flex-start", gap: 8, fontSize: 10, color: "#166534",
        }}>
          <span style={{ fontSize: 14, flexShrink: 0 }}>&#x1F512;</span>
          <div>
            <div style={{ fontWeight: 700, marginBottom: 2 }}>データ保護について</div>
            <div style={{ lineHeight: 1.5, color: "#15803D" }}>
              アップロードされたPDFはサーバーに保存されません（テキスト抽出後に即破棄）。
              AI抽出結果は参考値です。<strong>宅地建物取引士による最終確認が必要です。</strong>
            </div>
          </div>
        </div>

        <div style={{ padding: 20 }}>
          {/* ─── アップロード画面 ─── */}
          {step === "upload" && (
            <>
              <div
                onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setDragOver(true); }}
                onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); setDragOver(false); }}
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
                  ファイルをドラッグ&ドロップ
                </div>
                <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 4 }}>
                  またはクリックしてファイルを選択
                </div>
                <div style={{ fontSize: 10, color: "#94A3B8", marginTop: 8 }}>
                  対応: PDF / JPEG / PNG / WEBP / テキスト
                </div>
                <div style={{ fontSize: 9, color: "#2563EB", marginTop: 4 }}>
                  登記簿謄本・マイソク・契約書などをOCRで自動認識
                </div>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.txt,.jpg,.jpeg,.png,.webp,application/pdf,text/plain,image/*"
                  style={{ display: "none" }}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    console.log("[PDF] ファイル選択:", f?.name, f?.type, f?.size);
                    if (f) handleFile(f);
                    e.target.value = ""; // 同じファイルを再選択可能に
                  }}
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

          {/* ─── OCR処理中 ─── */}
          {step === "ocr" && (
            <div style={{ textAlign: "center", padding: "40px 20px" }}>
              <div style={{ fontSize: 28, marginBottom: 12, animation: "pulse 1.5s ease-in-out infinite" }}>
                🔍
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#334155" }}>
                画像PDFを文字認識中（OCR）
              </div>
              <div style={{ fontSize: 12, color: "#2563EB", marginTop: 8, fontWeight: 600 }}>
                {ocrProgress}
              </div>
              <div style={{ fontSize: 10, color: "#94A3B8", marginTop: 8, lineHeight: 1.5 }}>
                スキャンPDFから文字を認識しています。<br />
                ページ数に応じて数秒〜数十秒かかります。
              </div>
              <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }`}</style>
            </div>
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

              {/* AI免責注意 */}
              <div style={{
                marginTop: 12, padding: "8px 12px", borderRadius: 6,
                background: "#FFFBEB", border: "1px solid #FDE68A",
                fontSize: 10, color: "#92400E", lineHeight: 1.5,
              }}>
                <strong>&#x26A0; 重要：</strong>AI抽出データは参考値であり、正確性を保証するものではありません。
                宅地建物取引業法第35条に基づき、宅地建物取引士が内容を確認のうえ、
                必要に応じて修正してください。
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
