"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type { PropertyData } from "@/lib/types";

const BLANK = "___________";

function str(v: unknown): string {
  if (v == null || v === "") return BLANK;
  return String(v);
}

function yenStr(v: unknown): string {
  if (v == null || v === "") return BLANK;
  return `${Number(v).toLocaleString()} 円`;
}

function pctStr(v: unknown): string {
  if (v == null || v === "") return BLANK;
  return `${v} %`;
}

export default function PrintJusetsuPage() {
  const params = useParams();
  const id = params.id as string;
  const [property, setProperty] = useState<PropertyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`/api/properties/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then((data) => {
        if (data.error) {
          setError(data.error);
        } else {
          setProperty(data);
        }
        setLoading(false);
      })
      .catch(() => {
        setError("物件が見つかりません");
        setLoading(false);
      });
  }, [id]);

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 60, fontFamily: "'Noto Serif JP', serif" }}>
        読み込み中...
      </div>
    );
  }

  if (error || !property) {
    return (
      <div style={{ textAlign: "center", padding: 60, fontFamily: "'Noto Serif JP', serif" }}>
        <p>{error || "物件が見つかりません"}</p>
        <Link href={`/properties/${id}`}>戻る</Link>
      </div>
    );
  }

  const p = property;
  const pTypeLabel = p.property_type === "mansion" ? "区分マンション" : p.property_type === "land" ? "土地" : p.property_type === "house" ? "一戸建て" : "一棟";
  const isMansion = p.property_type === "mansion" || p.property_type === "condo";
  const today = new Date().toLocaleDateString("ja-JP", { year: "numeric", month: "long", day: "numeric" });

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;700&display=swap');

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body { background: #e0e0e0; }

        .jusetsu-container {
          font-family: 'Noto Serif JP', 'Yu Mincho', 'Hiragino Mincho ProN', serif;
          color: #000;
          line-height: 1.8;
          font-size: 11pt;
        }

        .jusetsu-page {
          width: 210mm;
          min-height: 297mm;
          padding: 15mm;
          margin: 10mm auto;
          background: #fff;
          box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }

        .jusetsu-title {
          text-align: center;
          font-size: 22pt;
          font-weight: 700;
          letter-spacing: 8px;
          border-bottom: 3px double #000;
          padding-bottom: 8mm;
          margin-bottom: 8mm;
        }

        .jusetsu-subtitle {
          text-align: center;
          font-size: 10pt;
          margin-bottom: 6mm;
          color: #333;
        }

        .jusetsu-date {
          text-align: right;
          font-size: 10pt;
          margin-bottom: 6mm;
        }

        .section-title {
          font-size: 12pt;
          font-weight: 700;
          background: #f0f0f0;
          padding: 2mm 4mm;
          border-left: 4px solid #000;
          margin: 6mm 0 3mm 0;
        }

        .section-number {
          display: inline-block;
          min-width: 24px;
          text-align: center;
          margin-right: 4px;
        }

        .info-table {
          width: 100%;
          border-collapse: collapse;
          margin-bottom: 4mm;
          font-size: 10pt;
        }

        .info-table th,
        .info-table td {
          border: 1px solid #333;
          padding: 2mm 3mm;
          vertical-align: top;
        }

        .info-table th {
          background: #f5f5f5;
          font-weight: 700;
          text-align: left;
          width: 35%;
          white-space: nowrap;
        }

        .info-table td {
          width: 65%;
        }

        .info-table .sub-header {
          background: #e8e8e8;
          font-weight: 700;
          text-align: center;
        }

        .sig-area {
          margin-top: 8mm;
          border: 1px solid #333;
          padding: 4mm;
        }

        .sig-row {
          display: flex;
          margin-bottom: 4mm;
          align-items: baseline;
        }

        .sig-label {
          width: 80px;
          font-weight: 700;
          font-size: 10pt;
          flex-shrink: 0;
        }

        .sig-line {
          flex: 1;
          border-bottom: 1px solid #666;
          min-height: 20px;
          margin-left: 4mm;
        }

        .no-print {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 1000;
          background: #0F172A;
          padding: 12px 24px;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .no-print button {
          padding: 8px 20px;
          border-radius: 6px;
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          border: none;
        }

        .print-btn { background: #2563EB; color: #fff; }
        .back-btn { background: #fff; color: #0F172A; border: 1.5px solid #CBD5E1 !important; }

        .footer-note {
          font-size: 9pt;
          color: #666;
          text-align: center;
          margin-top: 6mm;
          padding-top: 3mm;
          border-top: 1px solid #ccc;
        }

        @media print {
          body { background: #fff; }
          .no-print { display: none !important; }
          .jusetsu-page {
            box-shadow: none;
            margin: 0;
            padding: 0;
            width: 100%;
          }
          .print-page-break { page-break-before: always; }
          @page {
            size: A4 portrait;
            margin: 15mm;
          }
        }
      `}</style>

      {/* Print toolbar */}
      <div className="no-print">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ color: "#F8FAFC", fontSize: 14, fontWeight: 700 }}>重要事項説明書 プレビュー</span>
          <span style={{ color: "#94A3B8", fontSize: 12 }}>{p.address}</span>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <Link href={`/properties/${id}`}>
            <button className="back-btn">戻る</button>
          </Link>
          <button className="print-btn" onClick={() => window.print()}>
            印刷 / PDF保存
          </button>
        </div>
      </div>

      <div className="jusetsu-container" style={{ paddingTop: 60 }}>

        {/* === PAGE 1 === */}
        <div className="jusetsu-page">
          <div className="jusetsu-title">重 要 事 項 説 明 書</div>
          <div className="jusetsu-subtitle">
            宅地建物取引業法第35条に基づく重要事項の説明
          </div>
          <div className="jusetsu-date">
            説明日：{today}
          </div>

          <div className="jusetsu-subtitle" style={{ textAlign: "left", marginBottom: "4mm" }}>
            買主 {BLANK} 殿
          </div>
          <div style={{ fontSize: "10pt", marginBottom: "6mm" }}>
            下記の不動産の売買に関し、宅地建物取引業法第35条の規定に基づき、次のとおり重要事項を説明いたします。
            <br />説明を受け、内容を理解した上で、本書面に記名押印します。
          </div>

          {/* 宅建業者情報 */}
          <div className="sig-area" style={{ marginBottom: "6mm" }}>
            <div style={{ fontWeight: 700, fontSize: "10pt", marginBottom: "3mm" }}>宅地建物取引業者</div>
            <div className="sig-row">
              <span className="sig-label">商号</span>
              <span className="sig-line"></span>
            </div>
            <div className="sig-row">
              <span className="sig-label">代表者</span>
              <span className="sig-line"></span>
            </div>
            <div className="sig-row">
              <span className="sig-label">免許番号</span>
              <span className="sig-line"></span>
            </div>
            <div className="sig-row">
              <span className="sig-label">所在地</span>
              <span className="sig-line"></span>
            </div>
          </div>

          <div className="sig-area">
            <div style={{ fontWeight: 700, fontSize: "10pt", marginBottom: "3mm" }}>説明を行う宅地建物取引士</div>
            <div className="sig-row">
              <span className="sig-label">氏名</span>
              <span className="sig-line"></span>
              <span style={{ marginLeft: "4mm", fontSize: "9pt" }}>印</span>
            </div>
            <div className="sig-row">
              <span className="sig-label">登録番号</span>
              <span className="sig-line"></span>
            </div>
          </div>

          {/* 1. 物件の表示 */}
          <div className="section-title">
            <span className="section-number">1</span>取引物件に関する事項（物件の表示）
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>物件の所在地</th>
                <td>{str(p.address)}</td>
              </tr>
              <tr>
                <th>物件種別</th>
                <td>{pTypeLabel}</td>
              </tr>
              <tr>
                <th>土地面積</th>
                <td>{p.land_area ? `${p.land_area} ㎡` : BLANK}</td>
              </tr>
              <tr>
                <th>建物面積</th>
                <td>{p.building_area ? `${p.building_area} ㎡` : BLANK}</td>
              </tr>
              <tr>
                <th>所有者</th>
                <td>{str(p.owner_name)}</td>
              </tr>
              <tr>
                <th>抵当権等の設定</th>
                <td>{str(p.mortgage)}</td>
              </tr>
            </tbody>
          </table>

          {/* 2. 都市計画法・建築基準法 */}
          <div className="section-title">
            <span className="section-number">2</span>都市計画法・建築基準法に基づく制限
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>都市計画区域区分</th>
                <td>{str(p.urban_plan_zone)}</td>
              </tr>
              <tr>
                <th>用途地域</th>
                <td>{str(p.zoning)}</td>
              </tr>
              <tr>
                <th>建ぺい率</th>
                <td>{pctStr(p.building_coverage_ratio)}</td>
              </tr>
              <tr>
                <th>容積率</th>
                <td>{pctStr(p.floor_area_ratio)}</td>
              </tr>
              <tr>
                <th>防火地域</th>
                <td>{str(p.fire_zone)}</td>
              </tr>
              <tr>
                <th>高度地区</th>
                <td>{str(p.height_district)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* === PAGE 2 === */}
        <div className="jusetsu-page print-page-break">
          {/* 3. 道路に関する事項 */}
          <div className="section-title">
            <span className="section-number">3</span>道路に関する事項
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>接面道路の種別</th>
                <td>{str(p.road_type)}</td>
              </tr>
              <tr>
                <th>道路幅員</th>
                <td>{p.road_width ? `${p.road_width} m` : BLANK}</td>
              </tr>
              <tr>
                <th>接道間口</th>
                <td>{p.road_frontage ? `${p.road_frontage} m` : BLANK}</td>
              </tr>
            </tbody>
          </table>

          {/* 4. 飲用水等 */}
          <div className="section-title">
            <span className="section-number">4</span>飲用水・電気・ガスの供給施設及び排水施設
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>飲用水（上水道）</th>
                <td>{str(p.water_supply)}</td>
              </tr>
              <tr>
                <th>排水施設（下水道）</th>
                <td>{str(p.sewage)}</td>
              </tr>
              <tr>
                <th>ガス</th>
                <td>{str(p.gas_type)}</td>
              </tr>
              <tr>
                <th>電気</th>
                <td>{str(p.electricity)}</td>
              </tr>
            </tbody>
          </table>

          {/* 5. 宅地造成等規制法・津波 */}
          <div className="section-title">
            <span className="section-number">5</span>宅地造成等規制法・津波防災地域づくり法
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>洪水浸水想定区域</th>
                <td>{str(p.flood_text)}</td>
              </tr>
              <tr>
                <th>津波浸水想定</th>
                <td>{str(p.tsunami_text)}</td>
              </tr>
              <tr>
                <th>高潮浸水想定</th>
                <td>{str(p.hightide_text)}</td>
              </tr>
              <tr>
                <th>土砂災害警戒区域</th>
                <td>{str(p.landslide_text)}</td>
              </tr>
            </tbody>
          </table>

          {/* 6. 国土利用計画法・その他の法令制限 */}
          <div className="section-title">
            <span className="section-number">6</span>国土利用計画法・その他の法令に基づく制限
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>アスベスト調査</th>
                <td>{str(p.asbestos)}</td>
              </tr>
              <tr>
                <th>耐震診断</th>
                <td>{str(p.earthquake_resistance)}</td>
              </tr>
              <tr>
                <th>その他法令上の制限</th>
                <td>{BLANK}</td>
              </tr>
            </tbody>
          </table>

          {/* 7. 私道 */}
          <div className="section-title">
            <span className="section-number">7</span>私道に関する負担等
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>私道負担</th>
                <td>{str(p.private_road)}</td>
              </tr>
              <tr>
                <th>私道面積・負担金</th>
                <td>{BLANK}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* === PAGE 3 === */}
        <div className="jusetsu-page print-page-break">
          {/* 8. 取引条件 */}
          <div className="section-title">
            <span className="section-number">8</span>取引条件に関する事項（代金・交換差金以外に授受される金額）
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>売買代金</th>
                <td>{yenStr(p.price)}</td>
              </tr>
              <tr>
                <th>取引態様</th>
                <td>{str(p.transaction_type)}</td>
              </tr>
              <tr>
                <th>手付金</th>
                <td>{yenStr(p.earnest_money)}</td>
              </tr>
              <tr>
                <th>引渡予定日</th>
                <td>{str(p.delivery_date)}</td>
              </tr>
              <tr>
                <th>固定資産税等の精算</th>
                <td>引渡日を基準に日割精算する。（暦年 / 年度）</td>
              </tr>
              <tr>
                <th>その他の費用</th>
                <td>{BLANK}</td>
              </tr>
            </tbody>
          </table>

          {/* 9. 契約の解除 */}
          <div className="section-title">
            <span className="section-number">9</span>契約の解除に関する事項
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>手付解除</th>
                <td>買主は手付金を放棄し、売主は手付金の倍額を返還して契約を解除できる。</td>
              </tr>
              <tr>
                <th>契約違反による解除</th>
                <td>相手方が履行に着手した後は、違約金を支払うことにより契約を解除できる。</td>
              </tr>
              <tr>
                <th>特約による解除</th>
                <td>{p.special_terms || BLANK}</td>
              </tr>
            </tbody>
          </table>

          {/* 10. 損害賠償 */}
          <div className="section-title">
            <span className="section-number">10</span>損害賠償額の予定又は違約金に関する事項
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>違約金の額</th>
                <td>売買代金の {BLANK} % 相当額</td>
              </tr>
              <tr>
                <th>損害賠償額の予定</th>
                <td>{BLANK}</td>
              </tr>
            </tbody>
          </table>

          {/* 11. 手付金等の保全 */}
          <div className="section-title">
            <span className="section-number">11</span>手付金等の保全措置
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>保全措置の有無</th>
                <td>有 ・ 無</td>
              </tr>
              <tr>
                <th>保全措置の概要</th>
                <td>{BLANK}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* === PAGE 4 === */}
        <div className="jusetsu-page print-page-break">
          {/* 12. ローンのあっせん */}
          <div className="section-title">
            <span className="section-number">12</span>ローンのあっせんに関する事項
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>金融機関名</th>
                <td>{BLANK}</td>
              </tr>
              <tr>
                <th>融資金額</th>
                <td>{BLANK}</td>
              </tr>
              <tr>
                <th>融資期間</th>
                <td>{BLANK}</td>
              </tr>
              <tr>
                <th>金利</th>
                <td>{BLANK}</td>
              </tr>
              <tr>
                <th>ローン特約</th>
                <td>{BLANK}</td>
              </tr>
            </tbody>
          </table>

          {/* 13. 割賦販売 */}
          <div className="section-title">
            <span className="section-number">13</span>割賦販売に関する事項（該当する場合）
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>該当有無</th>
                <td>該当しない</td>
              </tr>
            </tbody>
          </table>

          {/* 14. 供託所 */}
          <div className="section-title">
            <span className="section-number">14</span>供託所等に関する説明
          </div>
          <table className="info-table">
            <tbody>
              <tr>
                <th>営業保証金の供託所</th>
                <td>{BLANK}</td>
              </tr>
              <tr>
                <th>保証協会の名称</th>
                <td>{BLANK}</td>
              </tr>
            </tbody>
          </table>

          {/* 告知事項 */}
          {(p.is_incident || p.disclosure_notes || p.incident_detail) && (
            <>
              <div className="section-title">
                告知事項
              </div>
              <table className="info-table">
                <tbody>
                  {p.is_incident && (
                    <tr>
                      <th>心理的瑕疵</th>
                      <td style={{ color: "#B91C1C", fontWeight: 700 }}>{p.incident_detail || "あり（詳細は別紙）"}</td>
                    </tr>
                  )}
                  {p.disclosure_notes && (
                    <tr>
                      <th>その他の告知事項</th>
                      <td>{p.disclosure_notes}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </>
          )}

          {/* マンション固有（区分所有建物の場合） */}
          {isMansion && (
            <>
              <div className="section-title">
                区分所有建物に関する事項
              </div>
              <table className="info-table">
                <tbody>
                  <tr>
                    <th>管理費（月額）</th>
                    <td>{yenStr(p.mgmt_fee)}</td>
                  </tr>
                  <tr>
                    <th>修繕積立金（月額）</th>
                    <td>{yenStr(p.repair_reserve)}</td>
                  </tr>
                  <tr>
                    <th>駐車場使用料（月額）</th>
                    <td>{yenStr(p.parking_fee)}</td>
                  </tr>
                  <tr>
                    <th>管理の形態</th>
                    <td>{str(p.mgmt_form)}</td>
                  </tr>
                  <tr>
                    <th>管理会社</th>
                    <td>{str(p.mgmt_company)}</td>
                  </tr>
                  <tr>
                    <th>総戸数</th>
                    <td>{p.total_units ? `${p.total_units} 戸` : BLANK}</td>
                  </tr>
                  <tr>
                    <th>大規模修繕計画</th>
                    <td>{str(p.major_repair_plan)}</td>
                  </tr>
                </tbody>
              </table>
            </>
          )}
        </div>

        {/* === PAGE 5: Signatures === */}
        <div className="jusetsu-page print-page-break">
          <div className="section-title">
            説明確認欄
          </div>
          <div style={{ fontSize: "10pt", marginTop: "4mm", marginBottom: "8mm" }}>
            上記の重要事項について、宅地建物取引士から説明を受け、内容を理解しました。
          </div>

          <div className="sig-area" style={{ marginBottom: "8mm" }}>
            <div style={{ fontWeight: 700, fontSize: "10pt", marginBottom: "4mm" }}>買主</div>
            <div className="sig-row">
              <span className="sig-label">住所</span>
              <span className="sig-line"></span>
            </div>
            <div className="sig-row">
              <span className="sig-label">氏名</span>
              <span className="sig-line"></span>
              <span style={{ marginLeft: "4mm", fontSize: "9pt" }}>印</span>
            </div>
            <div className="sig-row">
              <span className="sig-label">日付</span>
              <span className="sig-line">　　　年　　　月　　　日</span>
            </div>
          </div>

          <div className="sig-area" style={{ marginBottom: "8mm" }}>
            <div style={{ fontWeight: 700, fontSize: "10pt", marginBottom: "4mm" }}>売主</div>
            <div className="sig-row">
              <span className="sig-label">住所</span>
              <span className="sig-line"></span>
            </div>
            <div className="sig-row">
              <span className="sig-label">氏名</span>
              <span className="sig-line"></span>
              <span style={{ marginLeft: "4mm", fontSize: "9pt" }}>印</span>
            </div>
            <div className="sig-row">
              <span className="sig-label">日付</span>
              <span className="sig-line">　　　年　　　月　　　日</span>
            </div>
          </div>

          <div className="sig-area">
            <div style={{ fontWeight: 700, fontSize: "10pt", marginBottom: "4mm" }}>説明を行った宅地建物取引士</div>
            <div className="sig-row">
              <span className="sig-label">氏名</span>
              <span className="sig-line"></span>
              <span style={{ marginLeft: "4mm", fontSize: "9pt" }}>印</span>
            </div>
            <div className="sig-row">
              <span className="sig-label">登録番号</span>
              <span className="sig-line"></span>
            </div>
          </div>

          <div className="footer-note" style={{ marginTop: "12mm" }}>
            本書面は宅地建物取引業法第35条に基づく重要事項説明書です。
            <br />
            {BLANK} の箇所は説明時に記入してください。
          </div>

          {p.api_fetched_at && (
            <div className="footer-note">
              API取得日時: {new Date(p.api_fetched_at).toLocaleString("ja-JP")}
              　|　出力日時: {new Date().toLocaleString("ja-JP")}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
