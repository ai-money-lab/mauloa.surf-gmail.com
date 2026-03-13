"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type { PropertyData } from "@/lib/types";

/* ─── helpers ─── */
const B = "＿＿＿＿＿＿＿＿";
const BS = "＿＿＿＿";
const CHK = "☑";
const UNCHK = "☐";

function s(v: unknown): string { return v != null && v !== "" ? String(v) : ""; }
function sb(v: unknown): string { return s(v) || B; }
function yen(v: unknown): string { return v != null && v !== "" ? `${Number(v).toLocaleString()} 円` : B; }
function pct(v: unknown): string { return v != null && v !== "" ? `${v}%` : ""; }
function chk(v: unknown): string { return v ? CHK : UNCHK; }
function chkNot(v: unknown): string { return v ? UNCHK : CHK; }

type DocType = "jusetsu" | "rental" | "both";

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   全宅連準拠 重要事項説明書
   宅建業法第35条・施行規則 / 全宅連標準書式ベース
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

function JusetsuDocument({ p, today }: { p: PropertyData; today: string }) {
  const isMansion = p.property_type === "mansion" || p.property_type === "condo";
  const isRental = !!p.rent;
  const txLabel = isRental ? "建物の貸借" : isMansion ? "区分所有建物の売買・交換" : "土地建物の売買・交換";
  const pTypeLabel = isMansion ? "区分所有建物" : p.property_type === "land" ? "宅地" : p.property_type === "house" ? "建物（一戸建て）" : "一棟の建物";

  return (
    <>
      {/* ═══ A3見開き 1枚目（第一面＋第二面）═══ */}
      <div className="j-spread">
      <div className="j-page">
        <div className="j-title">重 要 事 項 説 明 書</div>
        <div className="j-sub">（{txLabel}）（第一面）</div>

        <table className="t w"><tbody>
          <tr>
            <td style={{ textAlign: "right", border: "none", padding: "0.5mm 0", fontSize: "8pt" }}>{today}</td>
          </tr>
          <tr>
            <td style={{ border: "none", padding: "0.5mm 0", fontSize: "8pt" }}>
              {isRental ? "賃借人" : "買主"}　{B}　殿
            </td>
          </tr>
        </tbody></table>

        <div className="j-text">
          下記の不動産について、宅地建物取引業法（以下「法」という。）第35条及び同法第35条の2の規定に基づき、次のとおり説明します。この内容は重要ですから、十分理解されるようお願いします。
        </div>

        {/* 宅建業者表示 */}
        <table className="t w">
          <thead><tr><th colSpan={6} className="hd">宅地建物取引業者の表示</th></tr></thead>
          <tbody>
            <tr>
              <th className="lbl">商号（名称）</th><td></td>
              <th className="lbl">免許証番号</th><td></td>
              <th className="lbl">取引態様</th>
              <td>{chk(false)} 売主{chk(false)} 代理{chk(true)} 媒介</td>
            </tr>
            <tr>
              <th className="lbl">主たる事務所</th><td colSpan={3}></td>
              <th className="lbl">電話番号</th><td></td>
            </tr>
            <tr>
              <th className="lbl">代表者氏名</th><td colSpan={5}></td>
            </tr>
          </tbody>
        </table>

        {/* 供託所 */}
        <table className="t w">
          <thead><tr><th colSpan={2} className="hd">供託所等に関する事項（法第35条の2）</th></tr></thead>
          <tbody>
            <tr>
              <td style={{ width: "50%", minHeight: "5mm" }}>{chk(false)} 営業保証金（供託所：{BS}）</td>
              <td>{chk(false)} 弁済業務保証金（保証協会：{BS}）</td>
            </tr>
          </tbody>
        </table>

        {/* 取引士 */}
        <table className="t w">
          <thead><tr><th colSpan={4} className="hd">説明をする宅地建物取引士</th></tr></thead>
          <tbody>
            <tr>
              <th className="lbl">氏名</th><td></td>
              <th className="lbl">登録番号</th><td></td>
            </tr>
          </tbody>
        </table>

        {/* Ⅰ */}
        <div className="part">Ⅰ　対象となる宅地又は建物に関する事項</div>

        {/* 1. 登記記録 */}
        <div className="item">１．登記記録に記録された事項</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="cat" rowSpan={4}>土<br/>地</th>
              <th className="lbl">所在・地番</th><td colSpan={3}>{sb(p.address)}</td>
            </tr>
            <tr>
              <th className="lbl">地目</th><td>{BS}</td>
              <th className="lbl">地積</th><td>{p.land_area ? `${p.land_area} ㎡` : BS}</td>
            </tr>
            <tr>
              <th className="lbl">所有者</th><td colSpan={3}>{sb(p.owner_name)}</td>
            </tr>
            <tr>
              <th className="lbl">権利関係</th><td colSpan={3}>抵当権：{s(p.mortgage) || "なし"}</td>
            </tr>
            <tr>
              <th className="cat" rowSpan={4}>建<br/>物</th>
              <th className="lbl">所在・家屋番号</th><td colSpan={3}>{sb(p.address)}</td>
            </tr>
            <tr>
              <th className="lbl">種類・構造</th><td>{pTypeLabel}</td>
              <th className="lbl">床面積</th><td>{p.building_area ? `${p.building_area} ㎡` : BS}</td>
            </tr>
            <tr>
              <th className="lbl">所有者</th><td colSpan={3}>{sb(p.owner_name)}</td>
            </tr>
            <tr>
              <th className="lbl">権利関係</th><td colSpan={3}>抵当権：{s(p.mortgage) || "なし"}</td>
            </tr>
          </tbody>
        </table>

        {/* 2. 法令 */}
        <div className="item">２．都市計画法・建築基準法等の法令に基づく制限の概要</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">都市計画区域</th>
              <td>{chk(p.urban_plan_zone)} 区域内（{s(p.urban_plan_zone) || BS}）　{chkNot(p.urban_plan_zone)} 区域外</td>
            </tr>
            <tr>
              <th className="lbl">用途地域</th>
              <td>{sb(p.zoning)}</td>
            </tr>
            <tr>
              <th className="lbl">建ぺい率／容積率</th>
              <td>建ぺい率　{pct(p.building_coverage_ratio) || BS}　　/　　容積率　{pct(p.floor_area_ratio) || BS}</td>
            </tr>
            <tr>
              <th className="lbl">防火地域</th>
              <td>
                {chk(s(p.fire_zone).includes("防火") && !s(p.fire_zone).includes("準"))} 防火地域
                {chk(s(p.fire_zone).includes("準防火"))} 準防火地域
                {chkNot(p.fire_zone)} 指定なし
              </td>
            </tr>
            <tr>
              <th className="lbl">高度地区</th>
              <td>{sb(p.height_district)}</td>
            </tr>
            <tr>
              <th className="lbl">その他の制限</th>
              <td>{B}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* ═══ 第二面 ═══ */}
      <div className="j-page">
        <div className="j-sub" style={{ textAlign: "right" }}>（第二面）</div>

        {/* 3. 私道 */}
        <div className="item">３．私道に関する負担等</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">私道の負担</th>
              <td>{chk(p.private_road)} 有（{s(p.private_road) || B}）　{chkNot(p.private_road)} 無</td>
            </tr>
          </tbody>
        </table>

        {/* 4. インフラ */}
        <div className="item">４．飲用水・電気・ガスの供給施設及び排水施設の整備状況</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">飲用水</th>
              <td>
                {chk(s(p.water_supply).includes("公営") || s(p.water_supply).includes("水道"))} 公営水道
                {chk(s(p.water_supply).includes("井戸"))} 私設（井戸水）
                {chkNot(p.water_supply)} 未確認
              </td>
            </tr>
            <tr>
              <th className="lbl">電気</th>
              <td>{sb(p.electricity)}</td>
            </tr>
            <tr>
              <th className="lbl">ガス</th>
              <td>
                {chk(s(p.gas_type).includes("都市"))} 都市ガス
                {chk(s(p.gas_type).includes("プロパン") || s(p.gas_type).includes("LP"))} LPガス
                {chk(s(p.gas_type).includes("なし") || s(p.gas_type).includes("個別"))} 個別方式
                {chkNot(p.gas_type)} 未確認
              </td>
            </tr>
            <tr>
              <th className="lbl">排水</th>
              <td>
                {chk(s(p.sewage).includes("公共"))} 公共下水
                {chk(s(p.sewage).includes("浄化槽"))} 浄化槽
                {chkNot(p.sewage)} 未確認
              </td>
            </tr>
          </tbody>
        </table>

        {/* 5. 接面道路 */}
        <div className="item">５．接面道路の状況</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">種別</th><td>{sb(p.road_type)}</td>
              <th className="lbl">幅員</th><td>{p.road_width ? `${p.road_width} m` : BS}</td>
              <th className="lbl">接道間口</th><td>{p.road_frontage ? `${p.road_frontage} m` : BS}</td>
            </tr>
          </tbody>
        </table>

        {isRental && (
          <>
            {/* 建物の設備（賃貸用） */}
            <div className="item">６．建物の設備の整備の状況</div>
            <table className="t w">
              <tbody>
                <tr>
                  <th className="lbl">台所</th><td>{chk(true)} 有　{UNCHK} 無</td>
                  <th className="lbl">浴室</th><td>{chk(true)} 有　{UNCHK} 無</td>
                  <th className="lbl">便所</th><td>{chk(true)} 有（{chk(true)} 水洗　{UNCHK} 汲取）</td>
                </tr>
                <tr>
                  <th className="lbl">洗面設備</th><td>{chk(true)} 有　{UNCHK} 無</td>
                  <th className="lbl">冷暖房</th><td>{B}</td>
                  <th className="lbl">その他</th><td>{B}</td>
                </tr>
              </tbody>
            </table>
          </>
        )}

        {/* 石綿・耐震 */}
        <div className="item">{isRental ? "７" : "６"}．石綿使用調査の内容</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">調査結果の記録</th>
              <td>
                {chk(p.asbestos)} 有（内容：{s(p.asbestos) || B}）
                {chkNot(p.asbestos)} 無
              </td>
            </tr>
          </tbody>
        </table>

        <div className="item">{isRental ? "８" : "７"}．耐震診断の内容</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">耐震診断</th>
              <td>
                {chk(p.earthquake_resistance)} 有（内容：{s(p.earthquake_resistance) || B}）
                {chkNot(p.earthquake_resistance)} 無
              </td>
            </tr>
          </tbody>
        </table>

        {/* 建物状況調査 */}
        <div className="item">{isRental ? "９" : "８"}．建物状況調査の結果の概要（既存の建物の場合）</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">調査の実施</th>
              <td>{UNCHK} 実施済（実施者：{B}　実施日：{B}）　{chk(true)} 未実施</td>
            </tr>
          </tbody>
        </table>

        {/* 災害区域 */}
        <div className="item">{isRental ? "10" : "９"}．土砂災害警戒区域内か否か</div>
        <table className="t w">
          <tbody>
            <tr>
              <td>
                {chk(Number(p.sediment_risk) > 0)} 区域内（{sb(p.landslide_text)}）
                {chk(!p.sediment_risk || Number(p.sediment_risk) === 0)} 区域外
              </td>
            </tr>
          </tbody>
        </table>

        <div className="item">{isRental ? "11" : "10"}．津波災害警戒区域内か否か</div>
        <table className="t w">
          <tbody>
            <tr>
              <td>
                {chk(Number(p.tsunami_level) > 0)} 区域内（{sb(p.tsunami_text)}）
                {chk(!p.tsunami_level || Number(p.tsunami_level) === 0)} 区域外
              </td>
            </tr>
          </tbody>
        </table>

        <div className="item">{isRental ? "12" : "11"}．造成宅地防災区域内か否か</div>
        <table className="t w">
          <tbody>
            <tr><td>{UNCHK} 区域内　{chk(true)} 区域外</td></tr>
          </tbody>
        </table>
      </div>
      </div>{/* /j-spread 1 */}

      {/* ═══ A3見開き 2枚目（第三面＋第四面）═══ */}
      <div className="j-spread">
      <div className="j-page">
        <div className="j-sub" style={{ textAlign: "right" }}>（第三面）</div>

        {/* 水害ハザードマップ */}
        <div className="item">{isRental ? "13" : "12"}．水防法に基づく水害ハザードマップにおける所在地</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">洪水</th>
              <td>{sb(p.flood_text)}</td>
            </tr>
            <tr>
              <th className="lbl">高潮</th>
              <td>{sb(p.hightide_text)}</td>
            </tr>
            <tr>
              <th className="lbl">津波</th>
              <td>{sb(p.tsunami_text)}</td>
            </tr>
          </tbody>
        </table>

        {/* マンション固有 */}
        {isMansion && !isRental && (
          <>
            <div className="item">13．区分所有建物の場合（一棟の建物又はその敷地に関する権利・管理・使用に関する事項）</div>
            <table className="t w">
              <tbody>
                <tr>
                  <th className="lbl">管理費（月額）</th><td>{yen(p.mgmt_fee)}</td>
                  <th className="lbl">修繕積立金（月額）</th><td>{yen(p.repair_reserve)}</td>
                </tr>
                <tr>
                  <th className="lbl">管理の形態</th><td>{sb(p.mgmt_form)}</td>
                  <th className="lbl">管理会社</th><td>{sb(p.mgmt_company)}</td>
                </tr>
                <tr>
                  <th className="lbl">総戸数</th><td>{p.total_units ? `${p.total_units} 戸` : BS}</td>
                  <th className="lbl">大規模修繕計画</th><td>{sb(p.major_repair_plan)}</td>
                </tr>
                <tr>
                  <th className="lbl">管理費等の滞納</th><td colSpan={3}>{B}</td>
                </tr>
              </tbody>
            </table>
          </>
        )}

        {/* Ⅱ */}
        <div className="part">Ⅱ　取引条件に関する事項</div>

        {isRental ? (
          /* ── 賃貸用 取引条件 ── */
          <>
            <div className="item">１．借賃以外に授受される金銭の額及び授受の目的</div>
            <table className="t w">
              <tbody>
                <tr>
                  <th className="lbl">賃料（月額）</th><td>{yen(p.rent)}</td>
                  <th className="lbl">共益費（月額）</th><td>{yen(p.common_area_fee)}</td>
                </tr>
                <tr>
                  <th className="lbl">敷金</th>
                  <td>{p.deposit_months ? `賃料の ${p.deposit_months} ヶ月分` : BS}</td>
                  <th className="lbl">礼金</th>
                  <td>{p.key_money_months ? `賃料の ${p.key_money_months} ヶ月分` : BS}</td>
                </tr>
                <tr>
                  <th className="lbl">支払時期</th><td>{sb(p.rent_payment_due)}</td>
                  <th className="lbl">支払方法</th><td>{sb(p.rent_payment_method)}</td>
                </tr>
              </tbody>
            </table>

            <div className="item">２．契約期間及び契約の更新に関する事項</div>
            <table className="t w">
              <tbody>
                <tr>
                  <th className="lbl">契約の種類</th>
                  <td colSpan={3}>
                    {chk(s(p.lease_type) !== "定期借家")} 普通建物賃貸借
                    {chk(s(p.lease_type) === "定期借家")} 定期建物賃貸借（借地借家法第38条）
                    {UNCHK} 終身建物賃貸借
                  </td>
                </tr>
                <tr>
                  <th className="lbl">契約期間</th>
                  <td colSpan={3}>
                    {s(p.lease_start) || BS}　から　{s(p.lease_end) || BS}まで（{p.lease_term_years ? `${p.lease_term_years}年間` : BS}）
                  </td>
                </tr>
                <tr>
                  <th className="lbl">更新</th>
                  <td colSpan={3}>
                    {s(p.lease_type) === "定期借家"
                      ? "本契約は期間の満了により終了し、更新がない。（借地借家法第38条）"
                      : "期間満了の1年前から6月前までに更新しない旨の通知がない場合、同一条件で更新。"
                    }
                  </td>
                </tr>
                {s(p.lease_type) !== "定期借家" && (
                  <tr>
                    <th className="lbl">更新料</th>
                    <td colSpan={3}>{sb(p.renewal_fee)}</td>
                  </tr>
                )}
              </tbody>
            </table>

            <div className="item">３．用途その他の利用の制限に関する事項</div>
            <table className="t w">
              <tbody>
                <tr>
                  <th className="lbl">使用目的</th><td>{sb(p.purpose_of_use)}</td>
                </tr>
                <tr>
                  <th className="lbl">ペット飼育</th>
                  <td>{chk(s(p.pet_allowed) === "可")} 可　{chk(s(p.pet_allowed) !== "可")} 不可　（{s(p.pet_allowed)}）</td>
                </tr>
                <tr>
                  <th className="lbl">喫煙</th><td>{sb(p.smoking_allowed)}</td>
                </tr>
                <tr>
                  <th className="lbl">転貸</th><td>{sb(p.sublease_allowed)}</td>
                </tr>
              </tbody>
            </table>

            <div className="item">４．敷金等の精算に関する事項</div>
            <table className="t w">
              <tbody>
                <tr>
                  <td>
                    {p.restoration_terms || "敷金は、未払賃料及び原状回復費用を控除した残額を返還する。通常の使用に伴う損耗及び経年変化は賃借人の負担としない。（民法第621条・第622条の2）"}
                  </td>
                </tr>
              </tbody>
            </table>

            <div className="item">５．管理の委託先</div>
            <table className="t w">
              <tbody>
                <tr>
                  <th className="lbl">管理会社</th><td>{sb(p.mgmt_company)}</td>
                  <th className="lbl">連絡先</th><td>{B}</td>
                </tr>
              </tbody>
            </table>
          </>
        ) : (
          /* ── 売買用 取引条件 ── */
          <>
            <div className="item">１．代金・交換差金以外に授受される金銭の額及び目的</div>
            <table className="t w">
              <tbody>
                <tr>
                  <th className="lbl">売買代金</th><td>{yen(p.price)}</td>
                  <th className="lbl">取引態様</th><td>{sb(p.transaction_type)}</td>
                </tr>
                <tr>
                  <th className="lbl">手付金</th><td>{yen(p.earnest_money)}</td>
                  <th className="lbl">引渡予定日</th><td>{sb(p.delivery_date)}</td>
                </tr>
                <tr>
                  <th className="lbl">固定資産税等</th><td colSpan={3}>引渡日を基準日として日割精算する。</td>
                </tr>
              </tbody>
            </table>

            <div className="item">２．契約の解除に関する事項</div>
            <table className="t w">
              <tbody>
                <tr><th className="lbl">手付解除</th><td>買主は手付金を放棄し、売主は手付金の倍額を返還して契約を解除できる。</td></tr>
                <tr><th className="lbl">契約違反</th><td>違約金を支払うことにより契約を解除できる。</td></tr>
                <tr><th className="lbl">ローン特約</th><td>融資の全部又は一部が不承認の場合、本契約は白紙解除とする。</td></tr>
              </tbody>
            </table>

            <div className="item">３．損害賠償額の予定又は違約金に関する事項</div>
            <table className="t w">
              <tbody>
                <tr><th className="lbl">違約金</th><td>売買代金の {BS} % 相当額</td></tr>
              </tbody>
            </table>

            <div className="item">４．手付金等の保全措置の概要</div>
            <table className="t w">
              <tbody>
                <tr><td>{UNCHK} 講ずる（方法：{B}）　{UNCHK} 講じない</td></tr>
              </tbody>
            </table>

            <div className="item">５．支払金又は預り金の保全措置の概要</div>
            <table className="t w">
              <tbody>
                <tr><td>{UNCHK} 講ずる（方法：{B}）　{UNCHK} 講じない</td></tr>
              </tbody>
            </table>

            <div className="item">６．金銭の貸借のあっせん</div>
            <table className="t w">
              <tbody>
                <tr>
                  <th className="lbl">金融機関</th><td>{B}</td>
                  <th className="lbl">融資金額</th><td>{B}</td>
                </tr>
                <tr>
                  <th className="lbl">返済方法</th><td>{B}</td>
                  <th className="lbl">金利</th><td>{B}</td>
                </tr>
              </tbody>
            </table>

            <div className="item">７．契約不適合責任の履行に関する措置の概要</div>
            <table className="t w">
              <tbody>
                <tr><td>{UNCHK} 講ずる（方法：{B}）　{UNCHK} 講じない</td></tr>
              </tbody>
            </table>
          </>
        )}
      </div>

      {/* ═══ 第四面 ═══ */}
      <div className="j-page">
        <div className="j-sub" style={{ textAlign: "right" }}>（第{isRental ? "四" : "四"}面）</div>

        {isRental && (
          <>
            <div className="item">６．損害賠償額の予定又は違約金に関する事項</div>
            <table className="t w">
              <tbody>
                <tr><td>{B}</td></tr>
              </tbody>
            </table>

            <div className="item">７．支払金又は預り金の保全措置の概要</div>
            <table className="t w">
              <tbody>
                <tr><td>{UNCHK} 講ずる（方法：{B}）　{UNCHK} 講じない</td></tr>
              </tbody>
            </table>

            <div className="item">８．保証人・保証会社</div>
            <table className="t w">
              <tbody>
                <tr>
                  <th className="lbl">連帯保証人</th>
                  <td>{chk(p.guarantor_required && p.guarantor_required !== "不要")} 要　{chk(!p.guarantor_required || p.guarantor_required === "不要")} 不要</td>
                </tr>
                {p.guarantor_required && p.guarantor_required !== "不要" && (
                  <tr><th className="lbl">極度額</th><td>{B}（民法第465条の2）</td></tr>
                )}
                <tr>
                  <th className="lbl">保証会社</th><td>{sb(p.guarantee_company)}</td>
                </tr>
                <tr>
                  <th className="lbl">火災保険</th><td>{sb(p.fire_insurance)}</td>
                </tr>
              </tbody>
            </table>
          </>
        )}

        {/* 告知事項 */}
        <div className="item">告知事項</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">心理的瑕疵</th>
              <td>
                {chk(p.is_incident)} 有（{s(p.incident_detail) || B}）　{chkNot(p.is_incident)} 無
              </td>
            </tr>
            <tr>
              <th className="lbl">その他告知事項</th>
              <td>{s(p.disclosure_notes) || "特になし"}</td>
            </tr>
          </tbody>
        </table>

        {/* 特約 */}
        <div className="item">特約事項</div>
        <div style={{ border: "0.5pt solid #000", padding: "1.5mm 2mm", minHeight: "18mm", fontSize: "8pt", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
          {s(p.special_terms)}
        </div>

        {/* 参考情報 */}
        <div className="item">参考情報（補足資料）</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">学区（小学校）</th><td>{sb(p.school_district)}</td>
              <th className="lbl">学区（中学校）</th><td>{sb(p.school_district_jr)}</td>
            </tr>
            <tr>
              <th className="lbl">公示地価</th><td>{p.land_price ? `${Number(p.land_price).toLocaleString()} 円/㎡` : BS}</td>
              <th className="lbl">調査年</th><td>{p.land_price_year ? `${p.land_price_year}年` : BS}</td>
            </tr>
            <tr>
              <th className="lbl">将来人口推計</th>
              <td colSpan={3}>
                {p.future_pop ? `現在 ${Math.round(p.future_pop).toLocaleString()}人` : ""}
                {p.future_pop_2050 ? ` → 2050年 ${Math.round(p.future_pop_2050).toLocaleString()}人` : ""}
                {p.future_pop_change != null ? `（${Number(p.future_pop_change) > 0 ? "+" : ""}${p.future_pop_change}%）` : ""}
              </td>
            </tr>
          </tbody>
        </table>

        {/* 署名 */}
        <div style={{ marginTop: "3mm", fontSize: "8pt", fontWeight: 700 }}>
          上記の内容について、宅地建物取引士より説明を受け、重要事項説明書の交付を受けました。
        </div>
        <table className="t w" style={{ marginTop: "2mm" }}>
          <tbody>
            <tr>
              <th className="cat">{isRental ? "賃借人" : "買主"}</th>
              <th className="lbl">住所</th><td colSpan={2}></td>
            </tr>
            <tr>
              <th className="cat"></th>
              <th className="lbl">氏名</th><td></td><td style={{ width: "10%", textAlign: "center" }}>印</td>
            </tr>
            <tr>
              <th className="cat"></th>
              <th className="lbl">日付</th><td colSpan={2}>　　年　　月　　日</td>
            </tr>
          </tbody>
        </table>

        <div className="j-footer">
          本書面は宅地建物取引業法第35条に基づく重要事項説明書です。
          {p.api_fetched_at && (
            <><br/>API取得日時：{new Date(p.api_fetched_at).toLocaleString("ja-JP")}　出力日時：{new Date().toLocaleString("ja-JP")}</>
          )}
        </div>
      </div>
      </div>{/* /j-spread 2 */}
    </>
  );
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   賃貸借契約書（宅建業法第37条/借地借家法/民法2020年改正対応）
   全宅連 住宅賃貸借契約書(A) 準拠
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

function RentalContractDocument({ p, today }: { p: PropertyData; today: string }) {
  const isMansion = p.property_type === "mansion" || p.property_type === "condo";
  const pTypeLabel = isMansion ? "区分所有建物" : p.property_type === "house" ? "建物（一戸建て）" : "一棟の建物";
  const isTeiki = s(p.lease_type) === "定期借家";

  return (
    <>
      {/* ═══ A3見開き（契約書 第一面＋第二面）═══ */}
      <div className="j-spread">
      <div className="j-page">
        <div className="j-title">{isTeiki ? "定期建物賃貸借契約書" : "住宅賃貸借契約書"}</div>
        <div className="j-sub">
          {isTeiki ? "（借地借家法第38条に基づく定期建物賃貸借契約）" : "（全宅連標準書式準拠）"}
        </div>
        <div style={{ textAlign: "right", fontSize: "8pt", marginBottom: "1.5mm" }}>契約日：{today}</div>

        <div className="j-text">
          賃貸人（以下「甲」という。）と賃借人（以下「乙」という。）とは、甲の所有する下記建物について、以下のとおり{isTeiki ? "定期" : ""}建物賃貸借契約を締結した。
        </div>

        {/* 当事者 */}
        <table className="t w">
          <thead><tr><th colSpan={4} className="hd">賃貸人（甲）</th></tr></thead>
          <tbody>
            <tr><th className="lbl">住所</th><td colSpan={3}></td></tr>
            <tr><th className="lbl">氏名（名称）</th><td></td><th className="lbl">電話</th><td></td></tr>
          </tbody>
          <thead><tr><th colSpan={4} className="hd">賃借人（乙）</th></tr></thead>
          <tbody>
            <tr><th className="lbl">住所</th><td colSpan={3}></td></tr>
            <tr><th className="lbl">氏名（名称）</th><td></td><th className="lbl">電話</th><td></td></tr>
          </tbody>
        </table>

        {/* 物件 */}
        <div className="item">（物件の表示）</div>
        <table className="t w">
          <tbody>
            <tr><th className="lbl">所在地</th><td colSpan={3}>{sb(p.address)}</td></tr>
            <tr>
              <th className="lbl">種別</th><td>{pTypeLabel}</td>
              <th className="lbl">面積</th><td>{p.building_area ? `${p.building_area} ㎡` : BS}</td>
            </tr>
            {isMansion && <tr><th className="lbl">部屋番号</th><td colSpan={3}>{B}</td></tr>}
            <tr><th className="lbl">構造・階数</th><td colSpan={3}>{B}</td></tr>
            <tr><th className="lbl">使用目的</th><td colSpan={3}>{sb(p.purpose_of_use) || "居住用"}</td></tr>
          </tbody>
        </table>

        {/* 契約期間 */}
        <div className="item">第１条（契約期間）</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">契約の種類</th>
              <td>{chkNot(isTeiki)} 普通建物賃貸借　{chk(isTeiki)} 定期建物賃貸借</td>
            </tr>
            <tr>
              <th className="lbl">契約期間</th>
              <td>{s(p.lease_start) || BS}　から　{s(p.lease_end) || BS}まで（{p.lease_term_years ? `${p.lease_term_years}年間` : BS}）</td>
            </tr>
          </tbody>
        </table>

        {/* 賃料 */}
        <div className="item">第２条（賃料等）</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">賃料（月額）</th><td>{yen(p.rent)}</td>
              <th className="lbl">共益費（月額）</th><td>{yen(p.common_area_fee)}</td>
            </tr>
            <tr>
              <th className="lbl">支払期日</th><td>{sb(p.rent_payment_due)}</td>
              <th className="lbl">支払方法</th>
              <td>
                {chk(s(p.rent_payment_method).includes("振込"))} 振込
                {chk(s(p.rent_payment_method).includes("振替"))} 口座振替
                {UNCHK} 持参
              </td>
            </tr>
          </tbody>
        </table>

        {/* 敷金・礼金 */}
        <div className="item">第３条（敷金等一時金）</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">敷金</th>
              <td>{p.deposit_months ? `賃料の ${p.deposit_months} ヶ月分${p.rent ? `（${(Number(p.rent) * Number(p.deposit_months)).toLocaleString()}円）` : ""}` : B}</td>
              <th className="lbl">礼金</th>
              <td>{p.key_money_months ? `賃料の ${p.key_money_months} ヶ月分${p.rent ? `（${(Number(p.rent) * Number(p.key_money_months)).toLocaleString()}円）` : ""}` : B}</td>
            </tr>
            {!isTeiki && (
              <tr><th className="lbl">更新料</th><td colSpan={3}>{sb(p.renewal_fee)}</td></tr>
            )}
            <tr><th className="lbl">火災保険</th><td colSpan={3}>{sb(p.fire_insurance)}</td></tr>
          </tbody>
        </table>
      </div>

      {/* ═══ 契約書 第二面 ═══ */}
      <div className="j-page">
        {/* 禁止事項 */}
        <div className="item">第４条（禁止又は制限される行為）</div>
        <table className="t w">
          <tbody>
            <tr><th className="lbl">ペット</th><td>{chk(s(p.pet_allowed) === "可")} 可　{chk(s(p.pet_allowed) !== "可")} 不可　{s(p.pet_allowed) && s(p.pet_allowed) !== "可" && s(p.pet_allowed) !== "不可" ? `（${p.pet_allowed}）` : ""}</td></tr>
            <tr><th className="lbl">喫煙</th><td>{sb(p.smoking_allowed)}</td></tr>
            <tr><th className="lbl">転貸</th><td>{sb(p.sublease_allowed) || "甲の書面による承諾なく転貸してはならない。（民法第612条）"}</td></tr>
          </tbody>
        </table>

        {/* 修繕 */}
        <div className="item">第５条（修繕）</div>
        <table className="t w">
          <tbody>
            <tr><th className="lbl">甲の修繕義務</th><td>乙の責めに帰すことのできない事由により修繕を要するときは、甲がこれを修繕する。（民法第606条）</td></tr>
            <tr><th className="lbl">乙の修繕権</th><td>甲が相当期間内に修繕しないとき、又は急迫の事情があるときは、乙が修繕できる。（民法第607条の2）</td></tr>
          </tbody>
        </table>

        {/* 解約 */}
        <div className="item">第６条（契約の解除・解約）</div>
        <table className="t w">
          <tbody>
            <tr><th className="lbl">乙からの解約</th><td>少なくとも {sb(p.cancellation_notice) || "1ヶ月"} 前に甲に書面で通知する。</td></tr>
            <tr><th className="lbl">甲からの解約</th><td>正当な事由をもって、少なくとも6ヶ月前に通知する。（借地借家法第28条）</td></tr>
            <tr><th className="lbl">即時解除事由</th><td>①3ヶ月以上の賃料滞納 ②禁止事項違反 ③反社会的勢力判明 ④信頼関係破壊</td></tr>
          </tbody>
        </table>

        {/* 原状回復 */}
        <div className="item">第７条（明渡し時の原状回復）</div>
        <table className="t w">
          <tbody>
            <tr>
              <td style={{ lineHeight: 1.4 }}>
                {p.restoration_terms || "通常の使用に伴い生じた損耗及び経年変化を除き、原状に回復して明け渡す。（民法第621条）"}
              </td>
            </tr>
          </tbody>
        </table>
        <table className="t w" style={{ marginTop: "0.5mm" }}>
          <thead>
            <tr>
              <th style={{ width: "50%", textAlign: "center", fontSize: "7.5pt" }}>賃借人の負担とならないもの（通常損耗）</th>
              <th style={{ width: "50%", textAlign: "center", fontSize: "7.5pt" }}>賃借人の負担となるもの</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ fontSize: "7pt", lineHeight: 1.4 }}>
                ・壁紙の日焼け、画鋲の穴<br/>・家具設置による床の凹み<br/>・テレビ等裏の電気やけ<br/>・設備機器の経年劣化
              </td>
              <td style={{ fontSize: "7pt", lineHeight: 1.4 }}>
                ・故意・過失による汚損・毀損<br/>・ペットによる傷・臭い<br/>・喫煙によるヤニ汚れ<br/>・清掃未実施のカビ・油汚れ
              </td>
            </tr>
          </tbody>
        </table>
        <div style={{ fontSize: "6.5pt", color: "#666", marginTop: "0.5mm" }}>※国土交通省「原状回復をめぐるトラブルとガイドライン（再改訂版）」準拠</div>

        {/* 保証 */}
        <div className="item">第８条（連帯保証人・保証会社）</div>
        <table className="t w">
          <tbody>
            <tr>
              <th className="lbl">連帯保証人</th>
              <td>{chk(p.guarantor_required && p.guarantor_required !== "不要")} 要　{chk(!p.guarantor_required || p.guarantor_required === "不要")} 不要</td>
            </tr>
            {p.guarantor_required && p.guarantor_required !== "不要" && (
              <tr><th className="lbl">極度額</th><td>{B}（民法第465条の2第1項）</td></tr>
            )}
            <tr><th className="lbl">保証会社</th><td>{sb(p.guarantee_company)}</td></tr>
          </tbody>
        </table>

        {/* 反社 */}
        <div className="item">第９条（反社会的勢力の排除）</div>
        <div style={{ fontSize: "7.5pt", lineHeight: 1.4, padding: "0.5mm 0" }}>
          甲及び乙は、自らが暴力団等反社会的勢力に該当しないことを表明し、将来にわたり該当しないことを確約する。違反した場合、催告なく解除できる。
        </div>
      </div>
      </div>{/* /j-spread 契約書1 */}

      {/* ═══ A3見開き（契約書 第三面＋余白）═══ */}
      <div className="j-spread">
      <div className="j-page">
        {/* 特約 */}
        <div className="item">第10条（特約事項）</div>
        <div style={{ border: "0.5pt solid #000", padding: "1.5mm 2mm", minHeight: "15mm", fontSize: "8pt", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
          {s(p.special_terms)}
        </div>

        {/* 告知 */}
        {(p.is_incident || p.disclosure_notes) && (
          <>
            <div className="item">告知事項</div>
            <table className="t w">
              <tbody>
                {p.is_incident && <tr><th className="lbl">心理的瑕疵</th><td style={{ color: "#B91C1C", fontWeight: 700, fontSize: "8pt" }}>{s(p.incident_detail) || "あり"}</td></tr>}
                {p.disclosure_notes && <tr><th className="lbl">その他</th><td>{p.disclosure_notes}</td></tr>}
              </tbody>
            </table>
          </>
        )}

        {isTeiki && (
          <div style={{ border: "1pt solid #000", padding: "2mm", marginTop: "2mm", fontSize: "7.5pt", lineHeight: 1.5 }}>
            <strong>【借地借家法第38条第3項に基づく説明書面】</strong><br/>
            本契約は定期建物賃貸借であり、契約の更新がなく、期間の満了により終了します。ただし、甲乙合意のうえ再契約することを妨げません。
            <div style={{ display: "flex", alignItems: "baseline", marginTop: "2mm" }}>
              <span style={{ fontWeight: 700, marginRight: "2mm", fontSize: "7.5pt" }}>上記説明を受けました　賃借人</span>
              <span style={{ flex: 1, borderBottom: "0.5pt solid #666", minHeight: 12 }}></span>
              <span style={{ marginLeft: "2mm", fontSize: "7.5pt" }}>印</span>
            </div>
          </div>
        )}

        {/* 署名 */}
        <div style={{ marginTop: "3mm", fontSize: "8pt", marginBottom: "2mm" }}>
          上記の契約を証するため、本書2通を作成し、甲乙署名捺印のうえ各1通を保有する。
        </div>

        <table className="t w">
          <thead><tr><th colSpan={4} className="hd">賃貸人（甲）</th></tr></thead>
          <tbody>
            <tr><th className="lbl">住所</th><td colSpan={3}></td></tr>
            <tr><th className="lbl">氏名</th><td></td><th style={{ width: "6%", textAlign: "center" }}>印</th><td style={{ width: "12%" }}></td></tr>
            <tr><th className="lbl">日付</th><td colSpan={3}>　　　年　　月　　日</td></tr>
          </tbody>
          <thead><tr><th colSpan={4} className="hd">賃借人（乙）</th></tr></thead>
          <tbody>
            <tr><th className="lbl">住所</th><td colSpan={3}></td></tr>
            <tr><th className="lbl">氏名</th><td></td><th style={{ textAlign: "center" }}>印</th><td></td></tr>
            <tr><th className="lbl">日付</th><td colSpan={3}>　　　年　　月　　日</td></tr>
          </tbody>
        </table>

        {p.guarantor_required && p.guarantor_required !== "不要" && (
          <table className="t w" style={{ marginTop: "2mm" }}>
            <thead><tr><th colSpan={4} className="hd">連帯保証人</th></tr></thead>
            <tbody>
              <tr><th className="lbl">住所</th><td colSpan={3}></td></tr>
              <tr><th className="lbl">氏名</th><td></td><th style={{ textAlign: "center" }}>印</th><td></td></tr>
              <tr><th className="lbl">極度額</th><td colSpan={3}>金　{B}　円（民法第465条の2第1項）</td></tr>
            </tbody>
          </table>
        )}

        <table className="t w" style={{ marginTop: "2mm" }}>
          <thead><tr><th colSpan={4} className="hd">媒介業者</th></tr></thead>
          <tbody>
            <tr><th className="lbl">商号</th><td></td><th className="lbl">免許番号</th><td></td></tr>
            <tr><th className="lbl">所在地</th><td colSpan={3}></td></tr>
            <tr><th className="lbl">取引士</th><td></td><th className="lbl">登録番号</th><td></td></tr>
          </tbody>
        </table>

        <div className="j-footer">
          {isTeiki ? "借地借家法第38条に基づく定期建物賃貸借契約書" : "民法及び借地借家法に基づく建物賃貸借契約書"}
          　/　民法（令和2年4月1日施行改正法）対応
        </div>
      </div>
      <div className="j-page">{/* 余白ページ（A3右半分）*/}</div>
      </div>{/* /j-spread 契約書2 */}
    </>
  );
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   メインページ
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

const isRental = (p: PropertyData) => !!p.rent;

export default function PrintPage() {
  const params = useParams();
  const id = params.id as string;
  const [property, setProperty] = useState<PropertyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [docType, setDocType] = useState<DocType>("both");

  useEffect(() => {
    fetch(`/api/properties/${id}`)
      .then((r) => { if (!r.ok) throw new Error("not found"); return r.json(); })
      .then((data) => {
        if (data.error) { setError(data.error); }
        else {
          setProperty(data);
          if (data.rent && !data.price) setDocType("both");
          else if (data.price && !data.rent) setDocType("jusetsu");
          else setDocType("both");
        }
        setLoading(false);
      })
      .catch(() => { setError("物件が見つかりません"); setLoading(false); });
  }, [id]);

  if (loading) return <div style={{ textAlign: "center", padding: 60, fontFamily: "'Noto Serif JP', serif" }}>読み込み中...</div>;
  if (error || !property) return (
    <div style={{ textAlign: "center", padding: 60, fontFamily: "'Noto Serif JP', serif" }}>
      <p>{error || "物件が見つかりません"}</p>
      <Link href={`/properties/${id}`}>戻る</Link>
    </div>
  );

  const p = property;
  const today = new Date().toLocaleDateString("ja-JP", { year: "numeric", month: "long", day: "numeric" });

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #ddd; }

        /* ── 全宅連準拠：実物書式ベース ── */
        .j-wrap { font-family: 'Noto Serif JP','Yu Mincho','Hiragino Mincho ProN','MS Mincho',serif; color: #000; line-height: 1.35; font-size: 8.5pt; }
        .j-spread { display: flex; width: 420mm; min-height: 297mm; margin: 6mm auto; background: #fff; box-shadow: 0 1px 6px rgba(0,0,0,.12); overflow: hidden; }
        .j-page { width: 210mm; min-height: 297mm; padding: 8mm 10mm; flex-shrink: 0; }
        .j-page + .j-page { border-left: 0.5pt solid #999; }

        .j-title { text-align: center; font-size: 14pt; font-weight: 700; letter-spacing: 8px; border-top: 1.5pt solid #000; border-bottom: 1.5pt solid #000; padding: 2mm 0; margin-bottom: 1.5mm; }
        .j-sub { text-align: center; font-size: 7.5pt; margin-bottom: 2mm; color: #000; }
        .j-text { font-size: 7.5pt; line-height: 1.5; margin-bottom: 2mm; }
        .j-footer { font-size: 6.5pt; color: #555; text-align: center; margin-top: 2mm; padding-top: 1mm; border-top: 0.5pt solid #999; }

        .part { font-size: 9pt; font-weight: 700; background: #000; color: #fff; padding: 1mm 3mm; margin: 3mm 0 1.5mm; letter-spacing: 1px; }
        .item { font-size: 8pt; font-weight: 700; background: #eee; padding: 0.8mm 2mm; border-left: 2pt solid #000; margin: 2mm 0 1mm; }

        .t { border-collapse: collapse; font-size: 8pt; }
        .t.w { width: 100%; }
        .t th, .t td { border: 0.5pt solid #000; padding: 0.6mm 1.5mm; vertical-align: top; line-height: 1.4; }
        .t .hd { background: #e0e0e0; text-align: center; font-size: 7.5pt; padding: 0.6mm; font-weight: 700; }
        .t .lbl { background: #f0f0f0; font-weight: 600; text-align: left; white-space: nowrap; width: 16%; font-size: 7.5pt; }
        .t .cat { background: #f0f0f0; font-weight: 600; text-align: center; width: 5%; vertical-align: middle; font-size: 7.5pt; }
        .t td { min-height: 4.5mm; }

        .toolbar { position: fixed; top: 0; left: 0; right: 0; z-index: 1000; background: #0F172A; padding: 8px 18px; display: flex; align-items: center; justify-content: space-between; }
        .toolbar button { padding: 6px 14px; border-radius: 5px; font-size: 11px; font-weight: 700; cursor: pointer; border: none; }
        .btn-p { background: #2563EB; color: #fff; }
        .btn-b { background: #fff; color: #0F172A; border: 1.5px solid #CBD5E1 !important; }
        .tab { padding: 5px 11px; border-radius: 5px; font-size: 11px; font-weight: 700; cursor: pointer; border: 1.5px solid #475569; background: transparent; color: #94A3B8; transition: all .15s; }
        .tab.on { background: #2563EB; border-color: #2563EB; color: #fff; }

        @media print {
          body { background: #fff; }
          .toolbar { display: none !important; }
          .j-spread { box-shadow: none; margin: 0; width: 100%; min-height: 0; }
          .j-page { width: 50%; min-height: 0; padding: 8mm 10mm; }
          .j-page + .j-page { border-left: 0.5pt solid #ccc; }
          .j-spread + .j-spread { page-break-before: always; }
          @page { size: A3 landscape; margin: 0; }
        }
      `}</style>

      <div className="toolbar">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: "#F8FAFC", fontSize: 12, fontWeight: 700 }}>書類出力</span>
          <span style={{ color: "#94A3B8", fontSize: 10 }}>{p.address}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <button className={`tab ${docType === "jusetsu" ? "on" : ""}`} onClick={() => setDocType("jusetsu")}>重説のみ</button>
          <button className={`tab ${docType === "rental" ? "on" : ""}`} onClick={() => setDocType("rental")}>契約書のみ</button>
          <button className={`tab ${docType === "both" ? "on" : ""}`} onClick={() => setDocType("both")}>両方</button>
          <span style={{ width: 1, height: 18, background: "#475569", margin: "0 2px" }} />
          <Link href={`/properties/${id}`}><button className="btn-b">戻る</button></Link>
          <button className="btn-p" onClick={() => window.print()}>印刷 / PDF保存</button>
        </div>
      </div>

      <div className="j-wrap" style={{ paddingTop: 48 }}>
        {(docType === "jusetsu" || docType === "both") && <JusetsuDocument p={p} today={today} />}
        {(docType === "rental" || docType === "both") && <RentalContractDocument p={p} today={today} />}
      </div>
    </>
  );
}
