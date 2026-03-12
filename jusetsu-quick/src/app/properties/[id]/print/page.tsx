"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type { PropertyData } from "@/lib/types";

const BLANK = "＿＿＿＿＿＿＿＿";
const BLANK_S = "＿＿＿＿";
const CHECK = "☑";
const UNCHECK = "☐";

function str(v: unknown): string {
  if (v == null || v === "") return "";
  return String(v);
}

function strOrBlank(v: unknown): string {
  if (v == null || v === "") return BLANK;
  return String(v);
}

function yenStr(v: unknown): string {
  if (v == null || v === "") return BLANK;
  return `${Number(v).toLocaleString()} 円`;
}

function pctStr(v: unknown): string {
  if (v == null || v === "") return "";
  return `${v}%`;
}

function check(v: unknown): string {
  return v ? CHECK : UNCHECK;
}

type DocType = "jusetsu" | "rental" | "both";

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 重要事項説明書（国交省標準様式 / 全宅連・全日準拠フォーマット）
// 宅地建物取引業法第35条・施行規則別記様式第16号の2 ベース
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function JusetsuDocument({ p, today }: { p: PropertyData; today: string }) {
  const pTypeLabel =
    p.property_type === "mansion" ? "区分所有建物" :
    p.property_type === "land" ? "宅地" :
    p.property_type === "house" ? "建物（一戸建て）" : "一棟の建物";
  const isMansion = p.property_type === "mansion" || p.property_type === "condo";
  const isRental = !!p.rent;
  const txType = isRental ? "賃貸借" : "売買";

  return (
    <>
      {/* ═══ 表紙 ═══ */}
      <div className="jusetsu-page">
        <div className="doc-header">重 要 事 項 説 明 書</div>
        <div className="doc-subheader">
          （宅地建物取引業法第35条に基づく重要事項説明書）
        </div>

        <table className="t full" style={{ marginTop: "6mm" }}>
          <tbody>
            <tr><td style={{ textAlign: "center", padding: "3mm", background: "#f8f8f8", fontWeight: 700 }}>
              説明年月日　{today}
            </td></tr>
          </tbody>
        </table>

        <div style={{ margin: "6mm 0 4mm", fontSize: "10.5pt" }}>
          {isRental ? "賃借人" : "買主"}（説明の相手方）　{BLANK}　殿
        </div>

        <div style={{ fontSize: "10pt", lineHeight: 1.9, marginBottom: "6mm" }}>
          下記の宅地又は建物の{txType}について、宅地建物取引業法第35条及び同法第35条の2の規定に基づき、
          次のとおり重要事項を説明します。この内容は重要ですので、十分理解されるようお願い申し上げます。
        </div>

        {/* 説明を行う宅建業者・取引士 */}
        <table className="t full">
          <thead><tr>
            <th colSpan={4} className="sec-head">説明をする宅地建物取引士</th>
          </tr></thead>
          <tbody>
            <tr>
              <th style={{ width: "15%" }}>商号（名称）</th>
              <td style={{ width: "35%" }}></td>
              <th style={{ width: "15%" }}>免許証番号</th>
              <td style={{ width: "35%" }}></td>
            </tr>
            <tr>
              <th>主たる事務所</th>
              <td colSpan={3}></td>
            </tr>
            <tr>
              <th>代表者氏名</th>
              <td></td>
              <th>電話番号</th>
              <td></td>
            </tr>
            <tr>
              <th colSpan={4} style={{ background: "#eee", textAlign: "center", fontSize: "9pt" }}>
                説明を行う取引士
              </th>
            </tr>
            <tr>
              <th>氏名</th>
              <td></td>
              <th>登録番号</th>
              <td></td>
            </tr>
          </tbody>
        </table>

        {/* ── Ⅰ 対象となる宅地又は建物に関する事項 ── */}
        <div className="part-title">Ⅰ　対象となる宅地又は建物に関する事項</div>

        {/* 1. 登記記録に記録された事項 */}
        <div className="item-title">１．登記記録に記録された事項</div>
        <table className="t full">
          <tbody>
            <tr>
              <th rowSpan={3} style={{ width: "10%", textAlign: "center", verticalAlign: "middle" }}>
                土地
              </th>
              <th style={{ width: "15%" }}>所在・地番</th>
              <td colSpan={3}>{strOrBlank(p.address)}</td>
            </tr>
            <tr>
              <th>地目</th>
              <td style={{ width: "20%" }}>{BLANK_S}</td>
              <th style={{ width: "15%" }}>地積</th>
              <td>{p.land_area ? `${p.land_area} ㎡` : BLANK_S}</td>
            </tr>
            <tr>
              <th>所有者</th>
              <td>{strOrBlank(p.owner_name)}</td>
              <th>持分</th>
              <td>{BLANK_S}</td>
            </tr>
            <tr>
              <th rowSpan={3} style={{ textAlign: "center", verticalAlign: "middle" }}>
                建物
              </th>
              <th>所在・家屋番号</th>
              <td colSpan={3}>{strOrBlank(p.address)}</td>
            </tr>
            <tr>
              <th>種類・構造</th>
              <td>{pTypeLabel}</td>
              <th>床面積</th>
              <td>{p.building_area ? `${p.building_area} ㎡` : BLANK_S}</td>
            </tr>
            <tr>
              <th>所有者</th>
              <td>{strOrBlank(p.owner_name)}</td>
              <th>持分</th>
              <td>{BLANK_S}</td>
            </tr>
            <tr>
              <th colSpan={2}>登記記録の<br/>権利関係</th>
              <td colSpan={3}>
                抵当権：{str(p.mortgage) || "なし / " + BLANK}
                <br/>
                その他：{BLANK}
              </td>
            </tr>
          </tbody>
        </table>

        {/* 2. 都市計画法・建築基準法等の法令に基づく制限 */}
        <div className="item-title">２．都市計画法・建築基準法等の法令に基づく制限の概要</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "25%" }}>都市計画区域の内外</th>
              <td>{check(p.urban_plan_zone)} 区域内（{strOrBlank(p.urban_plan_zone)}）　{check(!p.urban_plan_zone)} 区域外</td>
            </tr>
            <tr>
              <th>用途地域</th>
              <td>{strOrBlank(p.zoning)}</td>
            </tr>
            <tr>
              <th>建ぺい率 / 容積率</th>
              <td>
                建ぺい率 {pctStr(p.building_coverage_ratio) || BLANK_S}　/　容積率 {pctStr(p.floor_area_ratio) || BLANK_S}
              </td>
            </tr>
            <tr>
              <th>防火地域</th>
              <td>
                {check(str(p.fire_zone).includes("防火"))} 防火地域
                {check(str(p.fire_zone).includes("準防火"))} 準防火地域
                {check(!p.fire_zone)} 指定なし
                {p.fire_zone && !str(p.fire_zone).includes("防火") ? `（${p.fire_zone}）` : ""}
              </td>
            </tr>
            <tr>
              <th>高度地区</th>
              <td>{strOrBlank(p.height_district)}</td>
            </tr>
            <tr>
              <th>その他の制限</th>
              <td>{BLANK}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* ═══ PAGE 2 ═══ */}
      <div className="jusetsu-page print-page-break">
        {/* 3. 私道に関する負担 */}
        <div className="item-title">３．私道に関する負担等</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "25%" }}>私道の負担</th>
              <td>{check(p.private_road)} 有（{str(p.private_road) || BLANK}）　{check(!p.private_road)} 無</td>
            </tr>
          </tbody>
        </table>

        {/* 4. 飲用水・電気・ガスの供給施設及び排水施設 */}
        <div className="item-title">４．飲用水・電気・ガスの供給施設及び排水施設の整備状況</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "25%" }}>飲用水</th>
              <td style={{ width: "25%" }}>
                {check(str(p.water_supply).includes("公営"))} 公営水道
                {check(str(p.water_supply).includes("井戸"))} 井戸水
                {check(!p.water_supply)} 未確認
              </td>
              <th style={{ width: "25%" }}>電気</th>
              <td>{strOrBlank(p.electricity)}</td>
            </tr>
            <tr>
              <th>排水（下水道）</th>
              <td>
                {check(str(p.sewage).includes("公共"))} 公共下水
                {check(str(p.sewage).includes("浄化槽"))} 浄化槽
                {check(!p.sewage)} 未確認
              </td>
              <th>ガス</th>
              <td>
                {check(str(p.gas_type).includes("都市"))} 都市ガス
                {check(str(p.gas_type).includes("プロパン") || str(p.gas_type).includes("LP"))} LPガス
                {check(!p.gas_type)} 未確認
              </td>
            </tr>
            <tr>
              <th>整備予定・負担金</th>
              <td colSpan={3}>{BLANK}</td>
            </tr>
          </tbody>
        </table>

        {/* 5. 宅地造成 */}
        <div className="item-title">５．宅地造成又は建物建築の工事完了時における形状・構造</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "25%" }}>工事完了前の{txType}</th>
              <td>{check(false)} 該当する　{check(true)} 該当しない</td>
            </tr>
          </tbody>
        </table>

        {/* 6. 道路に関する事項 */}
        <div className="item-title">６．接面道路の状況</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "25%" }}>接面道路の種別</th>
              <td>{strOrBlank(p.road_type)}</td>
            </tr>
            <tr>
              <th>道路幅員</th>
              <td>{p.road_width ? `${p.road_width} m` : BLANK_S}</td>
            </tr>
            <tr>
              <th>接道間口</th>
              <td>{p.road_frontage ? `${p.road_frontage} m` : BLANK_S}</td>
            </tr>
            <tr>
              <th>建築基準法第42条</th>
              <td>{BLANK}</td>
            </tr>
          </tbody>
        </table>

        {/* 7. 災害区域 */}
        <div className="item-title">７．災害区域に関する事項</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "25%" }}>水防法<br/>（洪水浸水想定区域）</th>
              <td>{strOrBlank(p.flood_text)}</td>
            </tr>
            <tr>
              <th>津波防災地域づくり法<br/>（津波浸水想定）</th>
              <td>{strOrBlank(p.tsunami_text)}</td>
            </tr>
            <tr>
              <th>高潮浸水想定区域</th>
              <td>{strOrBlank(p.hightide_text)}</td>
            </tr>
            <tr>
              <th>土砂災害警戒区域</th>
              <td>{strOrBlank(p.landslide_text)}</td>
            </tr>
            <tr>
              <th>造成宅地防災区域</th>
              <td>{check(false)} 区域内　{check(true)} 区域外</td>
            </tr>
          </tbody>
        </table>

        {/* 8. アスベスト・耐震 */}
        <div className="item-title">８．石綿使用調査・耐震診断の内容</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "25%" }}>石綿（アスベスト）<br/>使用調査</th>
              <td>
                {check(p.asbestos)} 調査あり（結果：{str(p.asbestos) || BLANK}）
                <br/>
                {check(!p.asbestos)} 調査なし
              </td>
            </tr>
            <tr>
              <th>耐震診断</th>
              <td>
                {check(p.earthquake_resistance)} 実施済（結果：{str(p.earthquake_resistance) || BLANK}）
                <br/>
                {check(!p.earthquake_resistance)} 未実施
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* ═══ PAGE 3: マンション固有 + 取引条件 ═══ */}
      <div className="jusetsu-page print-page-break">
        {/* 区分所有建物（マンション） */}
        {isMansion && (
          <>
            <div className="item-title">９．区分所有建物の場合</div>
            <table className="t full">
              <tbody>
                <tr>
                  <th style={{ width: "25%" }}>管理費（月額）</th>
                  <td style={{ width: "25%" }}>{yenStr(p.mgmt_fee)}</td>
                  <th style={{ width: "25%" }}>修繕積立金（月額）</th>
                  <td>{yenStr(p.repair_reserve)}</td>
                </tr>
                <tr>
                  <th>駐車場使用料</th>
                  <td>{yenStr(p.parking_fee)}</td>
                  <th>総戸数</th>
                  <td>{p.total_units ? `${p.total_units} 戸` : BLANK_S}</td>
                </tr>
                <tr>
                  <th>管理の形態</th>
                  <td>{strOrBlank(p.mgmt_form)}</td>
                  <th>管理会社</th>
                  <td>{strOrBlank(p.mgmt_company)}</td>
                </tr>
                <tr>
                  <th>大規模修繕の予定</th>
                  <td colSpan={3}>{strOrBlank(p.major_repair_plan)}</td>
                </tr>
                <tr>
                  <th>管理費等の滞納</th>
                  <td colSpan={3}>{BLANK}</td>
                </tr>
              </tbody>
            </table>
          </>
        )}

        {/* ── Ⅱ 取引条件に関する事項 ── */}
        <div className="part-title">Ⅱ　取引条件に関する事項</div>

        {isRental ? (
          /* ── 賃貸借の取引条件 ── */
          <>
            <div className="item-title">{isMansion ? "10" : "９"}．賃料等の額並びにその支払の時期及び方法</div>
            <table className="t full">
              <tbody>
                <tr>
                  <th style={{ width: "25%" }}>賃料（月額）</th>
                  <td style={{ width: "25%" }}>{yenStr(p.rent)}</td>
                  <th style={{ width: "25%" }}>共益費（月額）</th>
                  <td>{yenStr(p.common_area_fee)}</td>
                </tr>
                <tr>
                  <th>支払時期</th>
                  <td>{strOrBlank(p.rent_payment_due)}</td>
                  <th>支払方法</th>
                  <td>{strOrBlank(p.rent_payment_method)}</td>
                </tr>
              </tbody>
            </table>

            <div className="item-title">{isMansion ? "11" : "10"}．敷金・礼金等</div>
            <table className="t full">
              <tbody>
                <tr>
                  <th style={{ width: "25%" }}>敷金</th>
                  <td style={{ width: "25%" }}>
                    {p.deposit_months ? `賃料の${p.deposit_months}ヶ月分` : BLANK_S}
                  </td>
                  <th style={{ width: "25%" }}>礼金</th>
                  <td>
                    {p.key_money_months ? `賃料の${p.key_money_months}ヶ月分` : BLANK_S}
                  </td>
                </tr>
                <tr>
                  <th>更新料</th>
                  <td>{strOrBlank(p.renewal_fee)}</td>
                  <th>火災保険</th>
                  <td>{strOrBlank(p.fire_insurance)}</td>
                </tr>
              </tbody>
            </table>

            <div className="item-title">{isMansion ? "12" : "11"}．契約期間及び契約の更新に関する事項</div>
            <table className="t full">
              <tbody>
                <tr>
                  <th style={{ width: "25%" }}>契約の種類</th>
                  <td>
                    {check(str(p.lease_type) !== "定期借家")} 普通建物賃貸借契約
                    {check(str(p.lease_type) === "定期借家")} 定期建物賃貸借契約（借地借家法第38条）
                  </td>
                </tr>
                <tr>
                  <th>契約期間</th>
                  <td>
                    {p.lease_start || BLANK_S}　から　{p.lease_end || BLANK_S}
                    まで（{p.lease_term_years ? `${p.lease_term_years}年間` : BLANK_S}）
                  </td>
                </tr>
                <tr>
                  <th>解約予告</th>
                  <td>{strOrBlank(p.cancellation_notice)}</td>
                </tr>
              </tbody>
            </table>

            <div className="item-title">{isMansion ? "13" : "12"}．用途その他の利用の制限に関する事項</div>
            <table className="t full">
              <tbody>
                <tr>
                  <th style={{ width: "25%" }}>使用目的</th>
                  <td>{strOrBlank(p.purpose_of_use)}</td>
                </tr>
                <tr>
                  <th>ペット飼育</th>
                  <td>{check(str(p.pet_allowed) === "可")} 可　{check(str(p.pet_allowed) !== "可")} 不可　備考：{str(p.pet_allowed)}</td>
                </tr>
                <tr>
                  <th>転貸</th>
                  <td>{strOrBlank(p.sublease_allowed)}</td>
                </tr>
              </tbody>
            </table>

            <div className="item-title">{isMansion ? "14" : "13"}．保証人・保証会社</div>
            <table className="t full">
              <tbody>
                <tr>
                  <th style={{ width: "25%" }}>連帯保証人</th>
                  <td>{strOrBlank(p.guarantor_required)}</td>
                </tr>
                <tr>
                  <th>保証会社</th>
                  <td>{strOrBlank(p.guarantee_company)}</td>
                </tr>
              </tbody>
            </table>
          </>
        ) : (
          /* ── 売買の取引条件 ── */
          <>
            <div className="item-title">{isMansion ? "10" : "９"}．代金及び交換差金以外に授受される金額</div>
            <table className="t full">
              <tbody>
                <tr>
                  <th style={{ width: "25%" }}>売買代金</th>
                  <td style={{ width: "25%" }}>{yenStr(p.price)}</td>
                  <th style={{ width: "25%" }}>手付金</th>
                  <td>{yenStr(p.earnest_money)}</td>
                </tr>
                <tr>
                  <th>取引態様</th>
                  <td>{strOrBlank(p.transaction_type)}</td>
                  <th>引渡予定日</th>
                  <td>{strOrBlank(p.delivery_date)}</td>
                </tr>
                <tr>
                  <th>固定資産税等</th>
                  <td colSpan={3}>引渡日を基準に日割精算する。</td>
                </tr>
              </tbody>
            </table>

            <div className="item-title">{isMansion ? "11" : "10"}．契約の解除に関する事項</div>
            <table className="t full">
              <tbody>
                <tr>
                  <th style={{ width: "25%" }}>手付解除</th>
                  <td>{isRental ? "—" : "買主は手付金を放棄し、売主は手付金の倍額を返還して契約を解除できる。"}</td>
                </tr>
                <tr>
                  <th>契約違反</th>
                  <td>違約金を支払うことにより契約を解除できる。</td>
                </tr>
                <tr>
                  <th>ローン特約</th>
                  <td>融資が不承認の場合、契約は白紙解除となる。</td>
                </tr>
              </tbody>
            </table>

            <div className="item-title">{isMansion ? "12" : "11"}．損害賠償額の予定又は違約金に関する事項</div>
            <table className="t full">
              <tbody>
                <tr>
                  <th style={{ width: "25%" }}>違約金</th>
                  <td>売買代金の {BLANK_S} % 相当額</td>
                </tr>
              </tbody>
            </table>

            <div className="item-title">{isMansion ? "13" : "12"}．手付金等の保全措置の概要</div>
            <table className="t full">
              <tbody>
                <tr>
                  <th style={{ width: "25%" }}>保全措置</th>
                  <td>{check(false)} 講ずる（方法：{BLANK}）　{check(false)} 講じない</td>
                </tr>
              </tbody>
            </table>

            <div className="item-title">{isMansion ? "14" : "13"}．金銭の貸借のあっせん</div>
            <table className="t full">
              <tbody>
                <tr>
                  <th style={{ width: "15%" }}>金融機関名</th>
                  <td style={{ width: "35%" }}>{BLANK}</td>
                  <th style={{ width: "15%" }}>融資金額</th>
                  <td>{BLANK}</td>
                </tr>
                <tr>
                  <th>返済方法</th>
                  <td>{BLANK}</td>
                  <th>金利</th>
                  <td>{BLANK}</td>
                </tr>
              </tbody>
            </table>
          </>
        )}
      </div>

      {/* ═══ PAGE 4: その他の事項 + 署名 ═══ */}
      <div className="jusetsu-page print-page-break">
        <div className="part-title">Ⅲ　その他の事項</div>

        {/* 供託所 */}
        <div className="item-title">供託所等に関する事項</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "25%" }}>営業保証金の<br/>供託所</th>
              <td>{BLANK}</td>
            </tr>
            <tr>
              <th>保証協会の名称</th>
              <td>{BLANK}</td>
            </tr>
          </tbody>
        </table>

        {/* 告知事項 */}
        <div className="item-title">告知事項（該当がある場合）</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "25%" }}>心理的瑕疵</th>
              <td>
                {check(p.is_incident)} 該当あり　{check(!p.is_incident)} 該当なし
                {p.is_incident && p.incident_detail && (
                  <div style={{ color: "#B91C1C", fontWeight: 700, marginTop: "2mm" }}>
                    内容：{p.incident_detail}
                  </div>
                )}
              </td>
            </tr>
            <tr>
              <th>その他の告知事項</th>
              <td>{str(p.disclosure_notes) || "特になし"}</td>
            </tr>
          </tbody>
        </table>

        {/* 特約 */}
        <div className="item-title">特約事項</div>
        <div style={{ border: "1px solid #333", padding: "3mm", minHeight: "25mm", fontSize: "10pt", whiteSpace: "pre-wrap", lineHeight: 1.8 }}>
          {p.special_terms || ""}
        </div>

        {/* 参考情報 */}
        <div className="item-title">参考情報（重要事項説明の補足資料）</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "25%" }}>学区（小学校）</th>
              <td style={{ width: "25%" }}>{strOrBlank(p.school_district)}</td>
              <th style={{ width: "25%" }}>学区（中学校）</th>
              <td>{strOrBlank(p.school_district_jr)}</td>
            </tr>
            <tr>
              <th>公示地価</th>
              <td>{p.land_price ? `${Number(p.land_price).toLocaleString()} 円/㎡` : BLANK_S}</td>
              <th>地価調査年</th>
              <td>{p.land_price_year ? `${p.land_price_year}年` : BLANK_S}</td>
            </tr>
            <tr>
              <th>将来人口推計</th>
              <td colSpan={3}>
                {p.future_pop ? `現在 ${Math.round(p.future_pop).toLocaleString()}人` : ""}
                {p.future_pop_2050 ? ` → 2050年 ${Math.round(p.future_pop_2050).toLocaleString()}人` : ""}
                {p.future_pop_change != null ? `（${p.future_pop_change > 0 ? "+" : ""}${p.future_pop_change}%）` : ""}
              </td>
            </tr>
          </tbody>
        </table>

        {/* 署名欄 */}
        <div style={{ marginTop: "8mm", fontSize: "10pt", marginBottom: "4mm", fontWeight: 700 }}>
          上記の重要事項の内容を確認し、説明を受けました。
        </div>

        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "12%", textAlign: "center" }} rowSpan={2}>{isRental ? "賃借人" : "買主"}</th>
              <th style={{ width: "12%" }}>住所</th>
              <td></td>
              <th style={{ width: "8%" }}>日付</th>
              <td style={{ width: "25%" }}>　　年　　月　　日</td>
            </tr>
            <tr>
              <th>氏名</th>
              <td></td>
              <th>印</th>
              <td></td>
            </tr>
            <tr>
              <th rowSpan={2} style={{ textAlign: "center" }}>{isRental ? "賃貸人" : "売主"}</th>
              <th>住所</th>
              <td></td>
              <th>日付</th>
              <td>　　年　　月　　日</td>
            </tr>
            <tr>
              <th>氏名</th>
              <td></td>
              <th>印</th>
              <td></td>
            </tr>
          </tbody>
        </table>

        <div className="footer-note" style={{ marginTop: "6mm" }}>
          本書面は宅地建物取引業法第35条に基づく重要事項説明書です。
          {p.api_fetched_at && (
            <>
              <br/>API取得日時: {new Date(p.api_fetched_at).toLocaleString("ja-JP")}　|　出力日時: {new Date().toLocaleString("ja-JP")}
            </>
          )}
        </div>
      </div>
    </>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 賃貸借契約書（宅建業法第37条 + 借地借家法 + 民法2020年改正対応）
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function RentalContractDocument({ p, today }: { p: PropertyData; today: string }) {
  const pTypeLabel =
    p.property_type === "mansion" ? "区分所有建物" :
    p.property_type === "land" ? "宅地" :
    p.property_type === "house" ? "建物（一戸建て）" : "一棟の建物";
  const isMansion = p.property_type === "mansion" || p.property_type === "condo";
  const isTeiki = p.lease_type === "定期借家";

  return (
    <>
      {/* === 契約書 PAGE 1 === */}
      <div className="jusetsu-page print-page-break">
        <div className="doc-header">
          {isTeiki ? "定期建物賃貸借契約書" : "建物賃貸借契約書"}
        </div>
        <div className="doc-subheader">
          {isTeiki
            ? "（借地借家法第38条に基づく定期建物賃貸借契約）"
            : "（民法・借地借家法に基づく建物賃貸借契約）"
          }
        </div>
        <div style={{ textAlign: "right", fontSize: "10pt", marginBottom: "4mm" }}>契約日：{today}</div>

        <div style={{ fontSize: "10pt", lineHeight: 1.9, marginBottom: "4mm" }}>
          賃貸人（以下「甲」という）と賃借人（以下「乙」という）は、以下のとおり建物賃貸借契約を締結する。
        </div>

        {/* 当事者 */}
        <div className="item-title">第１条（当事者）</div>
        <table className="t full">
          <thead><tr><th colSpan={4} className="sec-head">賃貸人（甲）</th></tr></thead>
          <tbody>
            <tr><th style={{ width: "15%" }}>住所</th><td colSpan={3}></td></tr>
            <tr><th>氏名（名称）</th><td></td><th style={{ width: "15%" }}>電話</th><td></td></tr>
          </tbody>
          <thead><tr><th colSpan={4} className="sec-head">賃借人（乙）</th></tr></thead>
          <tbody>
            <tr><th style={{ width: "15%" }}>住所</th><td colSpan={3}></td></tr>
            <tr><th>氏名（名称）</th><td></td><th style={{ width: "15%" }}>電話</th><td></td></tr>
          </tbody>
        </table>

        {/* 物件 */}
        <div className="item-title">第２条（賃貸借の目的物）</div>
        <table className="t full">
          <tbody>
            <tr><th style={{ width: "20%" }}>所在地</th><td colSpan={3}>{strOrBlank(p.address)}</td></tr>
            <tr>
              <th>種別</th><td>{pTypeLabel}</td>
              <th style={{ width: "15%" }}>面積</th><td>{p.building_area ? `${p.building_area} ㎡` : BLANK_S}</td>
            </tr>
            {isMansion && <tr><th>部屋番号</th><td colSpan={3}>{BLANK}</td></tr>}
            <tr><th>構造・階数</th><td colSpan={3}>{BLANK}</td></tr>
            <tr><th>使用目的</th><td colSpan={3}>{strOrBlank(p.purpose_of_use) || "居住用"}</td></tr>
          </tbody>
        </table>

        {/* 契約期間 */}
        <div className="item-title">第３条（契約期間）</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "20%" }}>契約の種類</th>
              <td>
                {check(!isTeiki)} 普通建物賃貸借
                {check(isTeiki)} 定期建物賃貸借（借地借家法第38条）
              </td>
            </tr>
            <tr>
              <th>契約期間</th>
              <td>
                {p.lease_start || BLANK_S}　から　{p.lease_end || BLANK_S}
                まで（{p.lease_term_years ? `${p.lease_term_years}年間` : BLANK_S}）
              </td>
            </tr>
          </tbody>
        </table>
        {isTeiki ? (
          <div style={{ fontSize: "9.5pt", padding: "2mm 3mm", border: "1px solid #999", marginTop: "2mm", lineHeight: 1.7 }}>
            本契約は、借地借家法第38条に規定する定期建物賃貸借であり、期間の満了により終了し、更新されません。
          </div>
        ) : (
          <div style={{ fontSize: "9.5pt", padding: "2mm 3mm", marginTop: "2mm", lineHeight: 1.7, color: "#555" }}>
            期間満了の1年前から6ヶ月前までに、更新しない旨の通知がない場合、同一条件で更新されるものとする。
          </div>
        )}
      </div>

      {/* === 契約書 PAGE 2 === */}
      <div className="jusetsu-page print-page-break">
        {/* 賃料等 */}
        <div className="item-title">第４条（賃料等）</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "20%" }}>賃料（月額）</th>
              <td style={{ width: "30%" }}>{yenStr(p.rent)}</td>
              <th style={{ width: "20%" }}>共益費（月額）</th>
              <td>{yenStr(p.common_area_fee)}</td>
            </tr>
            <tr>
              <th>合計月額</th>
              <td>{p.rent && p.common_area_fee
                ? `${(Number(p.rent) + Number(p.common_area_fee)).toLocaleString()} 円`
                : p.rent ? yenStr(p.rent) : BLANK
              }</td>
              <th>支払期日</th>
              <td>{strOrBlank(p.rent_payment_due)}</td>
            </tr>
            <tr>
              <th>支払方法</th>
              <td colSpan={3}>
                {check(str(p.rent_payment_method).includes("振込"))} 銀行振込
                {check(str(p.rent_payment_method).includes("振替"))} 口座振替
                {check(str(p.rent_payment_method).includes("持参"))} 持参払
                {check(!p.rent_payment_method)} その他
              </td>
            </tr>
          </tbody>
        </table>

        {/* 敷金・礼金 */}
        <div className="item-title">第５条（敷金・礼金等一時金）</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "20%" }}>敷金</th>
              <td style={{ width: "30%" }}>
                {p.deposit_months
                  ? `賃料の${p.deposit_months}ヶ月分（${p.rent ? `${(Number(p.rent) * Number(p.deposit_months)).toLocaleString()}円` : BLANK_S}）`
                  : BLANK
                }
              </td>
              <th style={{ width: "20%" }}>礼金</th>
              <td>
                {p.key_money_months
                  ? `賃料の${p.key_money_months}ヶ月分（${p.rent ? `${(Number(p.rent) * Number(p.key_money_months)).toLocaleString()}円` : BLANK_S}）`
                  : BLANK
                }
              </td>
            </tr>
            {!isTeiki && (
              <tr>
                <th>更新料</th>
                <td colSpan={3}>{strOrBlank(p.renewal_fee)}</td>
              </tr>
            )}
            <tr>
              <th>火災保険</th>
              <td colSpan={3}>{strOrBlank(p.fire_insurance)}</td>
            </tr>
          </tbody>
        </table>
        <div style={{ fontSize: "9pt", color: "#555", marginTop: "1mm", lineHeight: 1.7 }}>
          ※敷金は、賃貸借終了後、乙が物件を明け渡したとき、未払賃料・損害賠償額を控除し返還する。（民法第622条の2）
        </div>

        {/* 使用上の制限 */}
        <div className="item-title">第６条（禁止又は制限される行為）</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "20%" }}>ペット飼育</th>
              <td>{check(str(p.pet_allowed) === "可")} 可　{check(str(p.pet_allowed) !== "可")} 不可　{str(p.pet_allowed) && str(p.pet_allowed) !== "可" && str(p.pet_allowed) !== "不可" ? `（${p.pet_allowed}）` : ""}</td>
            </tr>
            <tr>
              <th>喫煙</th>
              <td>{strOrBlank(p.smoking_allowed)}</td>
            </tr>
            <tr>
              <th>転貸・又貸し</th>
              <td>{strOrBlank(p.sublease_allowed) || "甲の書面による承諾なく転貸してはならない。（民法第612条）"}</td>
            </tr>
          </tbody>
        </table>

        {/* 修繕 */}
        <div className="item-title">第７条（修繕）</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "20%" }}>甲の修繕義務</th>
              <td>甲は、乙の責めに帰すことのできない事由により修繕を要するときは、これを修繕する。（民法第606条）</td>
            </tr>
            <tr>
              <th>乙の修繕権</th>
              <td>甲が相当期間内に修繕しないとき、又は急迫の事情があるときは、乙が修繕できる。（民法第607条の2）</td>
            </tr>
          </tbody>
        </table>

        {/* 解約 */}
        <div className="item-title">第８条（契約の解除・解約）</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "20%" }}>乙からの解約</th>
              <td>少なくとも{strOrBlank(p.cancellation_notice) || "1ヶ月"}前に甲に書面で通知する。</td>
            </tr>
            <tr>
              <th>甲からの解約</th>
              <td>正当事由をもって、少なくとも6ヶ月前に通知する。（借地借家法第28条）</td>
            </tr>
            <tr>
              <th>即時解除</th>
              <td>
                ① 3ヶ月以上の賃料滞納　② 禁止事項違反　③ 反社会的勢力判明　④ 信頼関係破壊
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* === 契約書 PAGE 3 === */}
      <div className="jusetsu-page print-page-break">
        {/* 原状回復 */}
        <div className="item-title">第９条（明渡し・原状回復）</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "20%" }}>原状回復の範囲</th>
              <td>
                {p.restoration_terms || (
                  <>
                    通常の使用に伴い生じた損耗及び経年変化を除き、原状に回復する。（民法第621条）
                  </>
                )}
              </td>
            </tr>
          </tbody>
        </table>
        <table className="t full" style={{ marginTop: "2mm" }}>
          <thead>
            <tr>
              <th style={{ width: "50%", textAlign: "center" }}>賃借人の負担とならないもの（通常損耗）</th>
              <th style={{ width: "50%", textAlign: "center" }}>賃借人の負担となるもの</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ fontSize: "9.5pt", lineHeight: 1.7 }}>
                ・壁紙の日焼け、画鋲の穴<br/>
                ・家具設置による床の凹み<br/>
                ・テレビ・冷蔵庫裏の電気やけ<br/>
                ・設備機器の経年劣化
              </td>
              <td style={{ fontSize: "9.5pt", lineHeight: 1.7 }}>
                ・故意・過失による汚損・毀損<br/>
                ・ペットによる傷・臭い<br/>
                ・喫煙によるヤニ汚れ<br/>
                ・清掃未実施によるカビ・油汚れ
              </td>
            </tr>
          </tbody>
        </table>
        <div style={{ fontSize: "8.5pt", color: "#666", marginTop: "1mm" }}>
          ※国土交通省「原状回復をめぐるトラブルとガイドライン（再改訂版）」に準拠
        </div>

        {/* 保証 */}
        <div className="item-title">第10条（連帯保証人・保証会社）</div>
        <table className="t full">
          <tbody>
            <tr>
              <th style={{ width: "20%" }}>連帯保証人</th>
              <td>
                {check(p.guarantor_required && p.guarantor_required !== "不要")} 要
                {check(!p.guarantor_required || p.guarantor_required === "不要")} 不要
              </td>
            </tr>
            {p.guarantor_required && p.guarantor_required !== "不要" && (
              <tr>
                <th>極度額</th>
                <td>賃料の {BLANK_S} ヶ月分相当額（民法第465条の2）</td>
              </tr>
            )}
            <tr>
              <th>保証会社</th>
              <td>{strOrBlank(p.guarantee_company)}</td>
            </tr>
          </tbody>
        </table>

        {/* 反社条項 */}
        <div className="item-title">第11条（反社会的勢力の排除）</div>
        <div style={{ fontSize: "9.5pt", padding: "2mm 0", lineHeight: 1.8 }}>
          甲及び乙は、それぞれ相手方に対し、自己が暴力団、暴力団員、暴力団関係企業等の反社会的勢力に該当しないことを表明し、
          将来にわたっても該当しないことを確約する。相手方がこの表明に反した場合、催告なく直ちに本契約を解除できる。
        </div>

        {/* 特約 */}
        <div className="item-title">第12条（特約事項）</div>
        <div style={{ border: "1px solid #333", padding: "3mm", minHeight: "20mm", fontSize: "10pt", whiteSpace: "pre-wrap", lineHeight: 1.8 }}>
          {p.special_terms || ""}
        </div>

        {/* 告知 */}
        {(p.is_incident || p.disclosure_notes) && (
          <>
            <div className="item-title">告知事項</div>
            <table className="t full">
              <tbody>
                {p.is_incident && (
                  <tr><th style={{ width: "20%" }}>心理的瑕疵</th><td style={{ color: "#B91C1C", fontWeight: 700 }}>{p.incident_detail || "あり"}</td></tr>
                )}
                {p.disclosure_notes && (
                  <tr><th style={{ width: "20%" }}>その他</th><td>{p.disclosure_notes}</td></tr>
                )}
              </tbody>
            </table>
          </>
        )}

        {isTeiki && (
          <div style={{ border: "2px solid #333", padding: "4mm", marginTop: "4mm", fontSize: "9.5pt", lineHeight: 1.8 }}>
            <strong>【借地借家法第38条第3項に基づく説明書面】</strong><br/>
            本契約は定期建物賃貸借契約であり、契約の更新がなく、期間の満了により終了します。
            ただし、甲乙合意のうえ、再契約することを妨げません。<br/>
            <div className="sig-row" style={{ marginTop: "4mm" }}>
              <span className="sig-label">上記説明を受けました　賃借人</span>
              <span className="sig-line"></span>
              <span style={{ marginLeft: "4mm", fontSize: "9pt" }}>印</span>
            </div>
          </div>
        )}
      </div>

      {/* === 契約書 PAGE 4: 署名 === */}
      <div className="jusetsu-page print-page-break">
        <div style={{ fontSize: "10.5pt", marginBottom: "6mm", lineHeight: 1.8 }}>
          上記の契約条件を確認し、本契約の成立を証するため、本書2通を作成し、甲乙署名捺印のうえ、各1通を保有する。
        </div>

        <table className="t full">
          <thead><tr><th colSpan={4} className="sec-head">賃貸人（甲）</th></tr></thead>
          <tbody>
            <tr><th style={{ width: "12%" }}>住所</th><td colSpan={3}></td></tr>
            <tr>
              <th>氏名</th><td style={{ width: "38%" }}></td>
              <th style={{ width: "8%", textAlign: "center" }}>印</th><td style={{ width: "15%" }}></td>
            </tr>
            <tr><th>日付</th><td colSpan={3}>　　　　年　　月　　日</td></tr>
          </tbody>
          <thead><tr><th colSpan={4} className="sec-head">賃借人（乙）</th></tr></thead>
          <tbody>
            <tr><th style={{ width: "12%" }}>住所</th><td colSpan={3}></td></tr>
            <tr>
              <th>氏名</th><td></td>
              <th style={{ textAlign: "center" }}>印</th><td></td>
            </tr>
            <tr><th>日付</th><td colSpan={3}>　　　　年　　月　　日</td></tr>
          </tbody>
        </table>

        {/* 連帯保証人 */}
        {p.guarantor_required && p.guarantor_required !== "不要" && (
          <table className="t full" style={{ marginTop: "4mm" }}>
            <thead><tr><th colSpan={4} className="sec-head">連帯保証人</th></tr></thead>
            <tbody>
              <tr><th style={{ width: "12%" }}>住所</th><td colSpan={3}></td></tr>
              <tr>
                <th>氏名</th><td style={{ width: "38%" }}></td>
                <th style={{ width: "8%", textAlign: "center" }}>印</th><td style={{ width: "15%" }}></td>
              </tr>
              <tr>
                <th>極度額</th><td colSpan={3}>金　{BLANK}　円（民法第465条の2第1項）</td>
              </tr>
            </tbody>
          </table>
        )}

        {/* 仲介業者 */}
        <table className="t full" style={{ marginTop: "6mm" }}>
          <thead><tr><th colSpan={4} className="sec-head">媒介（仲介）業者</th></tr></thead>
          <tbody>
            <tr>
              <th style={{ width: "15%" }}>商号（名称）</th>
              <td style={{ width: "35%" }}></td>
              <th style={{ width: "15%" }}>免許番号</th>
              <td></td>
            </tr>
            <tr>
              <th>所在地</th>
              <td colSpan={3}></td>
            </tr>
            <tr>
              <th>取引士氏名</th>
              <td></td>
              <th>登録番号</th>
              <td></td>
            </tr>
          </tbody>
        </table>

        <div className="footer-note" style={{ marginTop: "8mm" }}>
          {isTeiki
            ? "本契約は借地借家法第38条に基づく定期建物賃貸借契約書です。"
            : "本契約は民法及び借地借家法に基づく建物賃貸借契約書です。"
          }
          <br/>民法（令和2年4月1日施行改正法）対応
        </div>
      </div>
    </>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// メインページ
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
          if (data.rent && !data.price) setDocType("both");
          else if (data.price && !data.rent) setDocType("jusetsu");
          else setDocType("both");
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
          line-height: 1.7;
          font-size: 10.5pt;
        }

        .jusetsu-page {
          width: 210mm;
          min-height: 297mm;
          padding: 12mm 15mm;
          margin: 8mm auto;
          background: #fff;
          box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }

        .doc-header {
          text-align: center;
          font-size: 20pt;
          font-weight: 700;
          letter-spacing: 6px;
          border-top: 2px solid #000;
          border-bottom: 2px solid #000;
          padding: 4mm 0;
          margin-bottom: 4mm;
        }

        .doc-subheader {
          text-align: center;
          font-size: 9.5pt;
          margin-bottom: 4mm;
          color: #333;
        }

        /* 大分類（Ⅰ、Ⅱ、Ⅲ） */
        .part-title {
          font-size: 13pt;
          font-weight: 700;
          background: #222;
          color: #fff;
          padding: 2.5mm 5mm;
          margin: 6mm 0 3mm 0;
          letter-spacing: 2px;
        }

        /* 項目タイトル */
        .item-title {
          font-size: 10.5pt;
          font-weight: 700;
          background: #f0f0f0;
          padding: 1.5mm 4mm;
          border-left: 3px solid #333;
          margin: 4mm 0 2mm 0;
        }

        /* 全宅連スタイルの表 */
        .t {
          border-collapse: collapse;
          font-size: 10pt;
        }
        .t.full { width: 100%; }
        .t th, .t td {
          border: 1px solid #333;
          padding: 1.5mm 2.5mm;
          vertical-align: top;
        }
        .t th {
          background: #f5f5f5;
          font-weight: 700;
          text-align: left;
          white-space: nowrap;
        }
        .t td { min-height: 7mm; }
        .t .sec-head {
          background: #ddd;
          text-align: center;
          font-size: 9.5pt;
          padding: 1.5mm;
        }

        /* 署名行 */
        .sig-row {
          display: flex;
          margin-bottom: 3mm;
          align-items: baseline;
        }
        .sig-label {
          font-weight: 700;
          font-size: 10pt;
          flex-shrink: 0;
          margin-right: 3mm;
        }
        .sig-line {
          flex: 1;
          border-bottom: 1px solid #666;
          min-height: 18px;
        }

        .footer-note {
          font-size: 8.5pt;
          color: #666;
          text-align: center;
          margin-top: 4mm;
          padding-top: 2mm;
          border-top: 1px solid #ccc;
        }

        /* ツールバー */
        .no-print {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 1000;
          background: #0F172A;
          padding: 10px 20px;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .no-print button {
          padding: 7px 16px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 700;
          cursor: pointer;
          border: none;
        }
        .print-btn { background: #2563EB; color: #fff; }
        .back-btn { background: #fff; color: #0F172A; border: 1.5px solid #CBD5E1 !important; }
        .doc-tab {
          padding: 5px 12px;
          border-radius: 5px;
          font-size: 11px;
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
            margin: 12mm 15mm;
          }
        }
      `}</style>

      {/* Toolbar */}
      <div className="no-print">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "#F8FAFC", fontSize: 13, fontWeight: 700 }}>書類出力</span>
          <span style={{ color: "#94A3B8", fontSize: 11 }}>{p.address}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button className={`doc-tab ${docType === "jusetsu" ? "active" : ""}`} onClick={() => setDocType("jusetsu")}>
            重説のみ
          </button>
          <button className={`doc-tab ${docType === "rental" ? "active" : ""}`} onClick={() => setDocType("rental")}>
            契約書のみ
          </button>
          <button className={`doc-tab ${docType === "both" ? "active" : ""}`} onClick={() => setDocType("both")}>
            両方
          </button>
          <span style={{ width: 1, height: 20, background: "#475569", margin: "0 2px" }} />
          <Link href={`/properties/${id}`}><button className="back-btn">戻る</button></Link>
          <button className="print-btn" onClick={() => window.print()}>印刷 / PDF保存</button>
        </div>
      </div>

      <div className="jusetsu-container" style={{ paddingTop: 52 }}>
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
