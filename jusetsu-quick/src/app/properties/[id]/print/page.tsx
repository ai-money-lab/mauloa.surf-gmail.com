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

type DocType = "jusetsu" | "rental" | "both";

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 重要事項説明書（宅建業法第35条）
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function JusetsuDocument({ p, today }: { p: PropertyData; today: string }) {
  const pTypeLabel =
    p.property_type === "mansion" ? "区分マンション" :
    p.property_type === "land" ? "土地" :
    p.property_type === "house" ? "一戸建て" : "一棟";
  const isMansion = p.property_type === "mansion" || p.property_type === "condo";

  return (
    <>
      {/* === PAGE 1 === */}
      <div className="jusetsu-page">
        <div className="jusetsu-title">重 要 事 項 説 明 書</div>
        <div className="jusetsu-subtitle">
          宅地建物取引業法第35条に基づく重要事項の説明
        </div>
        <div className="jusetsu-date">説明日：{today}</div>

        <div className="jusetsu-subtitle" style={{ textAlign: "left", marginBottom: "4mm" }}>
          {p.rent ? "賃借人" : "買主"} {BLANK} 殿
        </div>
        <div style={{ fontSize: "10pt", marginBottom: "6mm" }}>
          下記の不動産の{p.rent ? "賃貸借" : "売買"}に関し、宅地建物取引業法第35条の規定に基づき、次のとおり重要事項を説明いたします。
          <br />説明を受け、内容を理解した上で、本書面に記名押印します。
        </div>

        {/* 宅建業者情報 */}
        <div className="sig-area" style={{ marginBottom: "6mm" }}>
          <div style={{ fontWeight: 700, fontSize: "10pt", marginBottom: "3mm" }}>宅地建物取引業者</div>
          <div className="sig-row"><span className="sig-label">商号</span><span className="sig-line"></span></div>
          <div className="sig-row"><span className="sig-label">代表者</span><span className="sig-line"></span></div>
          <div className="sig-row"><span className="sig-label">免許番号</span><span className="sig-line"></span></div>
          <div className="sig-row"><span className="sig-label">所在地</span><span className="sig-line"></span></div>
        </div>

        <div className="sig-area">
          <div style={{ fontWeight: 700, fontSize: "10pt", marginBottom: "3mm" }}>説明を行う宅地建物取引士</div>
          <div className="sig-row">
            <span className="sig-label">氏名</span><span className="sig-line"></span>
            <span style={{ marginLeft: "4mm", fontSize: "9pt" }}>印</span>
          </div>
          <div className="sig-row"><span className="sig-label">登録番号</span><span className="sig-line"></span></div>
        </div>

        {/* 1. 物件の表示 */}
        <div className="section-title"><span className="section-number">1</span>取引物件に関する事項（物件の表示）</div>
        <table className="info-table"><tbody>
          <tr><th>物件の所在地</th><td>{str(p.address)}</td></tr>
          <tr><th>物件種別</th><td>{pTypeLabel}</td></tr>
          <tr><th>土地面積</th><td>{p.land_area ? `${p.land_area} ㎡` : BLANK}</td></tr>
          <tr><th>建物面積</th><td>{p.building_area ? `${p.building_area} ㎡` : BLANK}</td></tr>
          <tr><th>所有者</th><td>{str(p.owner_name)}</td></tr>
          <tr><th>抵当権等の設定</th><td>{str(p.mortgage)}</td></tr>
        </tbody></table>

        {/* 2. 都市計画法・建築基準法 */}
        <div className="section-title"><span className="section-number">2</span>都市計画法・建築基準法に基づく制限</div>
        <table className="info-table"><tbody>
          <tr><th>都市計画区域区分</th><td>{str(p.urban_plan_zone)}</td></tr>
          <tr><th>用途地域</th><td>{str(p.zoning)}</td></tr>
          <tr><th>建ぺい率</th><td>{pctStr(p.building_coverage_ratio)}</td></tr>
          <tr><th>容積率</th><td>{pctStr(p.floor_area_ratio)}</td></tr>
          <tr><th>防火地域</th><td>{str(p.fire_zone)}</td></tr>
          <tr><th>高度地区</th><td>{str(p.height_district)}</td></tr>
        </tbody></table>
      </div>

      {/* === PAGE 2 === */}
      <div className="jusetsu-page print-page-break">
        <div className="section-title"><span className="section-number">3</span>道路に関する事項</div>
        <table className="info-table"><tbody>
          <tr><th>接面道路の種別</th><td>{str(p.road_type)}</td></tr>
          <tr><th>道路幅員</th><td>{p.road_width ? `${p.road_width} m` : BLANK}</td></tr>
          <tr><th>接道間口</th><td>{p.road_frontage ? `${p.road_frontage} m` : BLANK}</td></tr>
        </tbody></table>

        <div className="section-title"><span className="section-number">4</span>飲用水・電気・ガスの供給施設及び排水施設</div>
        <table className="info-table"><tbody>
          <tr><th>飲用水（上水道）</th><td>{str(p.water_supply)}</td></tr>
          <tr><th>排水施設（下水道）</th><td>{str(p.sewage)}</td></tr>
          <tr><th>ガス</th><td>{str(p.gas_type)}</td></tr>
          <tr><th>電気</th><td>{str(p.electricity)}</td></tr>
        </tbody></table>

        <div className="section-title"><span className="section-number">5</span>災害区域に関する事項</div>
        <table className="info-table"><tbody>
          <tr><th>洪水浸水想定区域</th><td>{str(p.flood_text)}</td></tr>
          <tr><th>津波浸水想定</th><td>{str(p.tsunami_text)}</td></tr>
          <tr><th>高潮浸水想定</th><td>{str(p.hightide_text)}</td></tr>
          <tr><th>土砂災害警戒区域</th><td>{str(p.landslide_text)}</td></tr>
        </tbody></table>

        <div className="section-title"><span className="section-number">6</span>その他の法令に基づく制限</div>
        <table className="info-table"><tbody>
          <tr><th>アスベスト調査</th><td>{str(p.asbestos)}</td></tr>
          <tr><th>耐震診断</th><td>{str(p.earthquake_resistance)}</td></tr>
          <tr><th>その他法令上の制限</th><td>{BLANK}</td></tr>
        </tbody></table>

        <div className="section-title"><span className="section-number">7</span>私道に関する負担等</div>
        <table className="info-table"><tbody>
          <tr><th>私道負担</th><td>{str(p.private_road)}</td></tr>
          <tr><th>私道面積・負担金</th><td>{BLANK}</td></tr>
        </tbody></table>
      </div>

      {/* === PAGE 3 === */}
      <div className="jusetsu-page print-page-break">
        {p.rent ? (
          /* ── 賃貸借の場合の取引条件 ── */
          <>
            <div className="section-title"><span className="section-number">8</span>賃貸借の条件に関する事項</div>
            <table className="info-table"><tbody>
              <tr><th>賃料（月額）</th><td>{yenStr(p.rent)}</td></tr>
              <tr><th>共益費・管理費（月額）</th><td>{yenStr(p.common_area_fee)}</td></tr>
              <tr><th>敷金</th><td>{p.deposit_months ? `賃料の ${p.deposit_months} ヶ月分` : BLANK}</td></tr>
              <tr><th>礼金</th><td>{p.key_money_months ? `賃料の ${p.key_money_months} ヶ月分` : BLANK}</td></tr>
              <tr><th>契約期間</th><td>{p.lease_term_years ? `${p.lease_term_years} 年` : BLANK}</td></tr>
              <tr><th>契約形態</th><td>{str(p.lease_type)}</td></tr>
              <tr><th>賃料支払方法</th><td>{str(p.rent_payment_method)}</td></tr>
              <tr><th>賃料支払期日</th><td>{str(p.rent_payment_due)}</td></tr>
              <tr><th>更新料</th><td>{str(p.renewal_fee)}</td></tr>
              <tr><th>使用目的</th><td>{str(p.purpose_of_use)}</td></tr>
            </tbody></table>

            <div className="section-title"><span className="section-number">9</span>使用上の制限</div>
            <table className="info-table"><tbody>
              <tr><th>ペット飼育</th><td>{str(p.pet_allowed)}</td></tr>
              <tr><th>喫煙</th><td>{str(p.smoking_allowed)}</td></tr>
              <tr><th>転貸・又貸し</th><td>{str(p.sublease_allowed)}</td></tr>
            </tbody></table>

            <div className="section-title"><span className="section-number">10</span>契約の解除・原状回復</div>
            <table className="info-table"><tbody>
              <tr><th>解約予告期間</th><td>{str(p.cancellation_notice)}</td></tr>
              <tr><th>原状回復条件</th><td>{str(p.restoration_terms)}</td></tr>
              <tr><th>特約事項</th><td>{p.special_terms || BLANK}</td></tr>
            </tbody></table>

            <div className="section-title"><span className="section-number">11</span>保証・保険</div>
            <table className="info-table"><tbody>
              <tr><th>連帯保証人</th><td>{str(p.guarantor_required)}</td></tr>
              <tr><th>保証会社</th><td>{str(p.guarantee_company)}</td></tr>
              <tr><th>火災保険</th><td>{str(p.fire_insurance)}</td></tr>
            </tbody></table>
          </>
        ) : (
          /* ── 売買の場合の取引条件 ── */
          <>
            <div className="section-title"><span className="section-number">8</span>取引条件に関する事項</div>
            <table className="info-table"><tbody>
              <tr><th>売買代金</th><td>{yenStr(p.price)}</td></tr>
              <tr><th>取引態様</th><td>{str(p.transaction_type)}</td></tr>
              <tr><th>手付金</th><td>{yenStr(p.earnest_money)}</td></tr>
              <tr><th>引渡予定日</th><td>{str(p.delivery_date)}</td></tr>
              <tr><th>固定資産税等の精算</th><td>引渡日を基準に日割精算する。（暦年 / 年度）</td></tr>
              <tr><th>その他の費用</th><td>{BLANK}</td></tr>
            </tbody></table>

            <div className="section-title"><span className="section-number">9</span>契約の解除に関する事項</div>
            <table className="info-table"><tbody>
              <tr><th>手付解除</th><td>買主は手付金を放棄し、売主は手付金の倍額を返還して契約を解除できる。</td></tr>
              <tr><th>契約違反による解除</th><td>相手方が履行に着手した後は、違約金を支払うことにより契約を解除できる。</td></tr>
              <tr><th>特約による解除</th><td>{p.special_terms || BLANK}</td></tr>
            </tbody></table>

            <div className="section-title"><span className="section-number">10</span>損害賠償額の予定又は違約金に関する事項</div>
            <table className="info-table"><tbody>
              <tr><th>違約金の額</th><td>売買代金の {BLANK} % 相当額</td></tr>
              <tr><th>損害賠償額の予定</th><td>{BLANK}</td></tr>
            </tbody></table>

            <div className="section-title"><span className="section-number">11</span>手付金等の保全措置</div>
            <table className="info-table"><tbody>
              <tr><th>保全措置の有無</th><td>有 ・ 無</td></tr>
              <tr><th>保全措置の概要</th><td>{BLANK}</td></tr>
            </tbody></table>
          </>
        )}
      </div>

      {/* === PAGE 4 === */}
      <div className="jusetsu-page print-page-break">
        <div className="section-title"><span className="section-number">12</span>供託所等に関する説明</div>
        <table className="info-table"><tbody>
          <tr><th>営業保証金の供託所</th><td>{BLANK}</td></tr>
          <tr><th>保証協会の名称</th><td>{BLANK}</td></tr>
        </tbody></table>

        {(p.is_incident || p.disclosure_notes || p.incident_detail) && (
          <>
            <div className="section-title">告知事項</div>
            <table className="info-table"><tbody>
              {p.is_incident && (
                <tr><th>心理的瑕疵</th><td style={{ color: "#B91C1C", fontWeight: 700 }}>{p.incident_detail || "あり（詳細は別紙）"}</td></tr>
              )}
              {p.disclosure_notes && (
                <tr><th>その他の告知事項</th><td>{p.disclosure_notes}</td></tr>
              )}
            </tbody></table>
          </>
        )}

        {isMansion && (
          <>
            <div className="section-title">区分所有建物に関する事項</div>
            <table className="info-table"><tbody>
              <tr><th>管理費（月額）</th><td>{yenStr(p.mgmt_fee)}</td></tr>
              <tr><th>修繕積立金（月額）</th><td>{yenStr(p.repair_reserve)}</td></tr>
              <tr><th>駐車場使用料（月額）</th><td>{yenStr(p.parking_fee)}</td></tr>
              <tr><th>管理の形態</th><td>{str(p.mgmt_form)}</td></tr>
              <tr><th>管理会社</th><td>{str(p.mgmt_company)}</td></tr>
              <tr><th>総戸数</th><td>{p.total_units ? `${p.total_units} 戸` : BLANK}</td></tr>
              <tr><th>大規模修繕計画</th><td>{str(p.major_repair_plan)}</td></tr>
            </tbody></table>
          </>
        )}

        {/* 署名欄 */}
        <div className="section-title">説明確認欄</div>
        <div style={{ fontSize: "10pt", marginTop: "4mm", marginBottom: "6mm" }}>
          上記の重要事項について、宅地建物取引士から説明を受け、内容を理解しました。
        </div>

        <div className="sig-area" style={{ marginBottom: "6mm" }}>
          <div style={{ fontWeight: 700, fontSize: "10pt", marginBottom: "3mm" }}>{p.rent ? "賃借人" : "買主"}</div>
          <div className="sig-row"><span className="sig-label">住所</span><span className="sig-line"></span></div>
          <div className="sig-row">
            <span className="sig-label">氏名</span><span className="sig-line"></span>
            <span style={{ marginLeft: "4mm", fontSize: "9pt" }}>印</span>
          </div>
          <div className="sig-row"><span className="sig-label">日付</span><span className="sig-line">　　　年　　　月　　　日</span></div>
        </div>

        <div className="sig-area">
          <div style={{ fontWeight: 700, fontSize: "10pt", marginBottom: "3mm" }}>{p.rent ? "賃貸人" : "売主"}</div>
          <div className="sig-row"><span className="sig-label">住所</span><span className="sig-line"></span></div>
          <div className="sig-row">
            <span className="sig-label">氏名</span><span className="sig-line"></span>
            <span style={{ marginLeft: "4mm", fontSize: "9pt" }}>印</span>
          </div>
          <div className="sig-row"><span className="sig-label">日付</span><span className="sig-line">　　　年　　　月　　　日</span></div>
        </div>

        <div className="footer-note" style={{ marginTop: "8mm" }}>
          本書面は宅地建物取引業法第35条に基づく重要事項説明書です。
          <br />{BLANK} の箇所は説明時に記入してください。
        </div>
        {p.api_fetched_at && (
          <div className="footer-note">
            API取得日時: {new Date(p.api_fetched_at).toLocaleString("ja-JP")}　|　出力日時: {new Date().toLocaleString("ja-JP")}
          </div>
        )}
      </div>
    </>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 賃貸借契約書（宅建業法第37条 + 借地借家法 + 民法2020年改正対応）
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function RentalContractDocument({ p, today }: { p: PropertyData; today: string }) {
  const pTypeLabel =
    p.property_type === "mansion" ? "区分マンション" :
    p.property_type === "land" ? "土地" :
    p.property_type === "house" ? "一戸建て" : "一棟";
  const isMansion = p.property_type === "mansion" || p.property_type === "condo";
  const isTeiki = p.lease_type === "定期借家";

  return (
    <>
      {/* === 契約書 PAGE 1 === */}
      <div className="jusetsu-page print-page-break">
        <div className="jusetsu-title">
          {isTeiki ? "定期建物賃貸借契約書" : "建物賃貸借契約書"}
        </div>
        <div className="jusetsu-subtitle">
          {isTeiki
            ? "借地借家法第38条に基づく定期建物賃貸借契約"
            : "民法・借地借家法に基づく建物賃貸借契約"
          }
        </div>
        <div className="jusetsu-date">契約日：{today}</div>

        <div style={{ fontSize: "10pt", marginBottom: "6mm", lineHeight: 1.9 }}>
          賃貸人（以下「甲」という）と賃借人（以下「乙」という）は、以下のとおり建物賃貸借契約を締結する。
        </div>

        {/* 当事者 */}
        <div className="section-title"><span className="section-number">第1条</span>当事者の表示</div>
        <table className="info-table"><tbody>
          <tr><th colSpan={2} className="sub-header">賃貸人（甲）</th></tr>
          <tr><th>住所</th><td>{BLANK}</td></tr>
          <tr><th>氏名（名称）</th><td>{BLANK}</td></tr>
          <tr><th>電話番号</th><td>{BLANK}</td></tr>
          <tr><th colSpan={2} className="sub-header">賃借人（乙）</th></tr>
          <tr><th>住所</th><td>{BLANK}</td></tr>
          <tr><th>氏名（名称）</th><td>{BLANK}</td></tr>
          <tr><th>電話番号</th><td>{BLANK}</td></tr>
        </tbody></table>

        {/* 物件 */}
        <div className="section-title"><span className="section-number">第2条</span>賃貸借物件の表示</div>
        <table className="info-table"><tbody>
          <tr><th>物件の所在地</th><td>{str(p.address)}</td></tr>
          <tr><th>物件種別</th><td>{pTypeLabel}</td></tr>
          <tr><th>建物面積</th><td>{p.building_area ? `${p.building_area} ㎡` : BLANK}</td></tr>
          {isMansion && <tr><th>部屋番号</th><td>{BLANK}</td></tr>}
          <tr><th>構造・階数</th><td>{BLANK}</td></tr>
          <tr><th>建築年月</th><td>{BLANK}</td></tr>
          <tr><th>使用目的</th><td>{str(p.purpose_of_use) || "居住用"}</td></tr>
        </tbody></table>

        {/* 契約期間 */}
        <div className="section-title"><span className="section-number">第3条</span>契約期間</div>
        <table className="info-table"><tbody>
          <tr><th>契約形態</th><td>{str(p.lease_type) || "普通借家契約"}</td></tr>
          <tr><th>契約期間</th><td>{p.lease_term_years ? `${p.lease_term_years} 年間` : BLANK}</td></tr>
          <tr><th>契約開始日</th><td>{str(p.lease_start)}</td></tr>
          <tr><th>契約終了日</th><td>{str(p.lease_end)}</td></tr>
          {isTeiki ? (
            <tr><th>期間満了時</th><td>本契約は期間満了により終了し、更新はない。（借地借家法第38条）</td></tr>
          ) : (
            <tr><th>更新</th><td>期間満了の1年前から6ヶ月前までに、甲又は乙から相手方に対し、更新しない旨の通知がない場合は、同一条件で更新されるものとする。</td></tr>
          )}
        </tbody></table>
      </div>

      {/* === 契約書 PAGE 2 === */}
      <div className="jusetsu-page print-page-break">
        {/* 賃料等 */}
        <div className="section-title"><span className="section-number">第4条</span>賃料等</div>
        <table className="info-table"><tbody>
          <tr><th>賃料（月額）</th><td>{yenStr(p.rent)}</td></tr>
          <tr><th>共益費・管理費（月額）</th><td>{yenStr(p.common_area_fee)}</td></tr>
          <tr><th>合計月額</th><td>{p.rent && p.common_area_fee
            ? `${(Number(p.rent) + Number(p.common_area_fee)).toLocaleString()} 円`
            : p.rent ? yenStr(p.rent) : BLANK
          }</td></tr>
          <tr><th>支払方法</th><td>{str(p.rent_payment_method) || "口座振替"}</td></tr>
          <tr><th>支払期日</th><td>{str(p.rent_payment_due) || "毎月末日までに翌月分を支払う"}</td></tr>
        </tbody></table>

        {/* 敷金・礼金 */}
        <div className="section-title"><span className="section-number">第5条</span>敷金・礼金</div>
        <table className="info-table"><tbody>
          <tr><th>敷金</th><td>{p.deposit_months
            ? `賃料の ${p.deposit_months} ヶ月分（${p.rent ? `${(Number(p.rent) * Number(p.deposit_months)).toLocaleString()} 円` : BLANK}）`
            : BLANK
          }</td></tr>
          <tr><th>礼金</th><td>{p.key_money_months
            ? `賃料の ${p.key_money_months} ヶ月分（${p.rent ? `${(Number(p.rent) * Number(p.key_money_months)).toLocaleString()} 円` : BLANK}）`
            : BLANK
          }</td></tr>
          {!isTeiki && (
            <tr><th>更新料</th><td>{str(p.renewal_fee)}</td></tr>
          )}
        </tbody></table>
        <div style={{ fontSize: "9pt", color: "#555", marginTop: "2mm", marginBottom: "4mm" }}>
          ※敷金は、賃貸借契約が終了し、乙が物件を明け渡した後、未払賃料・原状回復費用等を控除した残額を返還する。（民法第622条の2）
        </div>

        {/* 禁止事項 */}
        <div className="section-title"><span className="section-number">第6条</span>禁止事項・使用上の制限</div>
        <table className="info-table"><tbody>
          <tr><th>転貸・又貸し</th><td>{str(p.sublease_allowed) || "甲の書面による承諾なく転貸してはならない（民法第612条）"}</td></tr>
          <tr><th>ペット飼育</th><td>{str(p.pet_allowed) || "不可"}</td></tr>
          <tr><th>喫煙</th><td>{str(p.smoking_allowed) || "室内禁煙"}</td></tr>
          <tr><th>その他</th><td>
            ① 共用部分への私物放置の禁止<br/>
            ② 騒音等近隣に迷惑を及ぼす行為の禁止<br/>
            ③ 危険物の持込・保管の禁止<br/>
            ④ 甲の承諾なく増改築・模様替えをしない
          </td></tr>
        </tbody></table>

        {/* 修繕 */}
        <div className="section-title"><span className="section-number">第7条</span>修繕</div>
        <table className="info-table"><tbody>
          <tr><th>甲の修繕義務</th><td>甲は、乙の責めに帰すことができない事由により修繕が必要となった場合は、速やかに修繕を行う。（民法第606条）</td></tr>
          <tr><th>乙の修繕権</th><td>甲が相当期間内に修繕しない場合、又は急迫の事情がある場合は、乙は自ら修繕することができる。（民法第607条の2）</td></tr>
          <tr><th>小規模修繕</th><td>畳の表替え、障子・襖の張替え、電球・ヒューズ等の消耗品の交換は乙の負担とする。</td></tr>
        </tbody></table>
      </div>

      {/* === 契約書 PAGE 3 === */}
      <div className="jusetsu-page print-page-break">
        {/* 契約の解除 */}
        <div className="section-title"><span className="section-number">第8条</span>契約の解除</div>
        <table className="info-table"><tbody>
          <tr><th>乙からの解約</th><td>乙は、{str(p.cancellation_notice) || "1ヶ月"}前までに甲に書面で通知することにより、本契約を解約できる。</td></tr>
          <tr><th>甲からの解約</th><td>甲は、正当な事由がある場合に限り、6ヶ月前までに乙に通知して契約を解約できる。（借地借家法第28条）</td></tr>
          <tr><th>即時解除事由</th><td>
            ① 賃料を3ヶ月以上滞納したとき<br/>
            ② 本契約の禁止事項に違反したとき<br/>
            ③ 反社会的勢力であることが判明したとき<br/>
            ④ 信頼関係を破壊する行為があったとき
          </td></tr>
        </tbody></table>

        {/* 原状回復 */}
        <div className="section-title"><span className="section-number">第9条</span>明渡し・原状回復</div>
        <table className="info-table"><tbody>
          <tr><th>原状回復の範囲</th><td>
            {p.restoration_terms || (
              <>
                乙は、通常の使用に伴い生じた損耗及び経年変化を除き、原状に回復して物件を明け渡すものとする。（民法第621条）
                <br/><br/>
                <strong>【通常損耗に該当するもの（乙の負担なし）】</strong><br/>
                ・壁紙の日焼け、画鋲の穴等の軽微な損傷<br/>
                ・家具設置による床の凹み<br/>
                ・設備機器の経年劣化<br/><br/>
                <strong>【乙の負担となるもの】</strong><br/>
                ・故意又は過失による汚損・毀損<br/>
                ・ペット飼育（許可物件の場合）による損傷<br/>
                ・喫煙によるヤニ汚れ・臭い
              </>
            )}
          </td></tr>
        </tbody></table>

        {/* 保証 */}
        <div className="section-title"><span className="section-number">第10条</span>連帯保証人・保証会社</div>
        <table className="info-table"><tbody>
          <tr><th>連帯保証人</th><td>{str(p.guarantor_required)}</td></tr>
          <tr><th>保証会社</th><td>{str(p.guarantee_company)}</td></tr>
          {p.guarantor_required && p.guarantor_required !== "不要" && (
            <tr><th>極度額</th><td>賃料の {BLANK} ヶ月分（民法第465条の2　個人根保証契約の極度額）</td></tr>
          )}
          <tr><th>火災保険</th><td>{str(p.fire_insurance)}</td></tr>
        </tbody></table>

        {/* 反社条項 */}
        <div className="section-title"><span className="section-number">第11条</span>反社会的勢力の排除</div>
        <div style={{ fontSize: "10pt", padding: "2mm 0", lineHeight: 1.8 }}>
          甲及び乙は、自らが暴力団、暴力団員、暴力団関係企業、総会屋等の反社会的勢力に該当しないことを表明し、
          将来にわたっても該当しないことを確約する。相手方がこれに違反した場合、催告なく直ちに本契約を解除できる。
        </div>
      </div>

      {/* === 契約書 PAGE 4 === */}
      <div className="jusetsu-page print-page-break">
        {/* 特約 */}
        <div className="section-title"><span className="section-number">第12条</span>特約事項</div>
        <div style={{ minHeight: "30mm", padding: "3mm", border: "1px solid #333", fontSize: "10pt", whiteSpace: "pre-wrap", lineHeight: 1.8 }}>
          {p.special_terms || "（特約なし）"}
        </div>

        {isTeiki && (
          <>
            <div className="section-title" style={{ marginTop: "8mm" }}>
              【定期借家契約に関する説明事項】
            </div>
            <div style={{ fontSize: "10pt", lineHeight: 1.8, border: "2px solid #333", padding: "4mm" }}>
              <strong>借地借家法第38条第3項に基づく説明</strong><br/><br/>
              本契約は、同法第38条に規定する定期建物賃貸借契約であり、契約の更新がなく、
              期間の満了により賃貸借は終了します。<br/><br/>
              ただし、甲及び乙が合意する場合は、期間満了後に新たな契約（再契約）を
              締結することは妨げられません。<br/><br/>
              上記について、契約締結前に書面を交付して説明を受けました。
              <div className="sig-row" style={{ marginTop: "6mm" }}>
                <span className="sig-label">賃借人</span><span className="sig-line"></span>
                <span style={{ marginLeft: "4mm", fontSize: "9pt" }}>印</span>
              </div>
            </div>
          </>
        )}

        {/* 告知事項 */}
        {(p.is_incident || p.disclosure_notes || p.incident_detail) && (
          <>
            <div className="section-title" style={{ marginTop: "6mm" }}>告知事項</div>
            <table className="info-table"><tbody>
              {p.is_incident && (
                <tr><th>心理的瑕疵</th><td style={{ color: "#B91C1C", fontWeight: 700 }}>{p.incident_detail || "あり（詳細は別紙）"}</td></tr>
              )}
              {p.disclosure_notes && (
                <tr><th>その他の告知事項</th><td>{p.disclosure_notes}</td></tr>
              )}
            </tbody></table>
          </>
        )}

        {/* 署名 */}
        <div style={{ marginTop: "8mm", fontSize: "10pt", marginBottom: "6mm" }}>
          上記の契約内容に合意し、本契約書2通を作成し、甲乙各1通を保有する。
        </div>

        <div className="sig-area" style={{ marginBottom: "6mm" }}>
          <div style={{ fontWeight: 700, fontSize: "10pt", marginBottom: "3mm" }}>賃貸人（甲）</div>
          <div className="sig-row"><span className="sig-label">住所</span><span className="sig-line"></span></div>
          <div className="sig-row">
            <span className="sig-label">氏名</span><span className="sig-line"></span>
            <span style={{ marginLeft: "4mm", fontSize: "9pt" }}>印</span>
          </div>
          <div className="sig-row"><span className="sig-label">日付</span><span className="sig-line">　　　年　　　月　　　日</span></div>
        </div>

        <div className="sig-area" style={{ marginBottom: "6mm" }}>
          <div style={{ fontWeight: 700, fontSize: "10pt", marginBottom: "3mm" }}>賃借人（乙）</div>
          <div className="sig-row"><span className="sig-label">住所</span><span className="sig-line"></span></div>
          <div className="sig-row">
            <span className="sig-label">氏名</span><span className="sig-line"></span>
            <span style={{ marginLeft: "4mm", fontSize: "9pt" }}>印</span>
          </div>
          <div className="sig-row"><span className="sig-label">日付</span><span className="sig-line">　　　年　　　月　　　日</span></div>
        </div>

        {/* 仲介業者 */}
        <div className="sig-area">
          <div style={{ fontWeight: 700, fontSize: "10pt", marginBottom: "3mm" }}>仲介業者（宅地建物取引業者）</div>
          <div className="sig-row"><span className="sig-label">商号</span><span className="sig-line"></span></div>
          <div className="sig-row"><span className="sig-label">免許番号</span><span className="sig-line"></span></div>
          <div className="sig-row"><span className="sig-label">取引士</span><span className="sig-line"></span></div>
        </div>

        <div className="footer-note" style={{ marginTop: "8mm" }}>
          {isTeiki
            ? "本契約は借地借家法第38条に基づく定期建物賃貸借契約書です。"
            : "本契約は民法及び借地借家法に基づく建物賃貸借契約書です。"
          }
          <br />
          民法（2020年4月1日施行改正法）対応
          <br />
          {BLANK} の箇所は契約時に記入してください。
        </div>
      </div>
    </>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// メインページ
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

export default function PrintPage() {
  const params = useParams();
  const id = params.id as string;
  const [property, setProperty] = useState<PropertyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [docType, setDocType] = useState<DocType>("both");

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
          // Auto-select doc type based on data
          if (data.rent && !data.price) {
            setDocType("both"); // Rental: show both (重説 + 契約書)
          } else if (data.price && !data.rent) {
            setDocType("jusetsu"); // Sale: just 重説
          } else {
            setDocType("both");
          }
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

        .info-table td { width: 65%; }

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

        .doc-tab {
          padding: 6px 14px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 700;
          cursor: pointer;
          border: 1.5px solid #475569;
          background: transparent;
          color: #94A3B8;
          transition: all 0.15s;
        }
        .doc-tab.active {
          background: #2563EB;
          border-color: #2563EB;
          color: #fff;
        }

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

      {/* Toolbar */}
      <div className="no-print">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ color: "#F8FAFC", fontSize: 14, fontWeight: 700 }}>書類プレビュー</span>
          <span style={{ color: "#94A3B8", fontSize: 12 }}>{p.address}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {/* Doc type tabs */}
          <button
            className={`doc-tab ${docType === "jusetsu" ? "active" : ""}`}
            onClick={() => setDocType("jusetsu")}
          >
            重説のみ
          </button>
          <button
            className={`doc-tab ${docType === "rental" ? "active" : ""}`}
            onClick={() => setDocType("rental")}
          >
            契約書のみ
          </button>
          <button
            className={`doc-tab ${docType === "both" ? "active" : ""}`}
            onClick={() => setDocType("both")}
          >
            両方出力
          </button>

          <span style={{ width: 1, height: 24, background: "#475569", margin: "0 4px" }} />

          <Link href={`/properties/${id}`}>
            <button className="back-btn">戻る</button>
          </Link>
          <button className="print-btn" onClick={() => window.print()}>
            印刷 / PDF保存
          </button>
        </div>
      </div>

      <div className="jusetsu-container" style={{ paddingTop: 60 }}>
        {(docType === "jusetsu" || docType === "both") && (
          <JusetsuDocument p={p} today={today} />
        )}
        {(docType === "rental" || docType === "both") && (
          <RentalContractDocument p={p} today={today} />
        )}
      </div>
    </>
  );
}
