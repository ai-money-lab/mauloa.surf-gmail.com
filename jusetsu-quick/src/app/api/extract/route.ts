import { NextRequest, NextResponse } from "next/server";
import { getRequestContext } from "@cloudflare/next-on-pages";
import { writeAuditLog } from "@/lib/db/queries";
import { ensureSchema } from "@/lib/db/ensure-schema";

export const runtime = "edge";

/* ─── 抽出プロンプト ─── */
const SYSTEM_PROMPT = `あなたは日本の不動産書類からデータを抽出する専門AIです。
与えられたテキストから不動産物件の情報を読み取り、JSON形式で返してください。

抽出するフィールド（該当する値がある場合のみ）：
- address: 所在地・住所
- owner_name: 所有者名・登記名義人
- land_area: 土地面積（㎡の数値のみ）
- building_area: 建物面積・専有面積（㎡の数値のみ）
- property_type: 物件種別（"mansion", "house", "land", "building" のいずれか）
- mortgage: 抵当権の内容
- zoning: 用途地域
- building_coverage_ratio: 建ぺい率（%の数値のみ）
- floor_area_ratio: 容積率（%の数値のみ）
- fire_zone: 防火地域（"防火地域", "準防火地域", "指定なし"）
- road_type: 接面道路の種別
- road_width: 道路幅員（mの数値のみ）
- water_supply: 飲用水（"公営水道", "井戸水" 等）
- sewage: 排水（"公共下水", "浄化槽" 等）
- gas_type: ガス（"都市ガス", "LPガス" 等）
- electricity: 電気
- price: 売買代金（円の数値のみ）
- rent: 賃料月額（円の数値のみ）
- common_area_fee: 共益費月額（円の数値のみ）
- deposit_months: 敷金（月数の数値のみ）
- key_money_months: 礼金（月数の数値のみ）
- mgmt_fee: 管理費月額（円の数値のみ）
- repair_reserve: 修繕積立金月額（円の数値のみ）
- total_units: 総戸数（数値のみ）
- mgmt_form: 管理形態
- mgmt_company: 管理会社名
- lease_start: 契約開始日（YYYY-MM-DD形式）
- lease_end: 契約終了日（YYYY-MM-DD形式）
- lease_type: 契約種類（"普通借家" or "定期借家"）
- transaction_type: 取引態様（"媒介", "代理", "売主" 等）
- earnest_money: 手付金（円の数値のみ）
- delivery_date: 引渡予定日
- special_terms: 特約事項

重要なルール：
1. 値が見つからないフィールドは含めない
2. 数値フィールドには単位（円、㎡、%等）を含めず数値のみ返す
3. 必ず有効なJSONのみ返す（説明文やマークダウンは不要）
4. テキストに複数物件がある場合は最初の物件のみ抽出
5. 「document_type」フィールドに書類の種類を推定して含める（"登記簿謄本", "マイソク", "賃貸契約書", "重要事項説明書", "その他"）`;

const USER_PROMPT = (text: string) =>
  `以下の不動産書類テキストからデータを抽出してJSON形式で返してください。\n\n---\n${text}\n---`;

/* ─── ルールベース抽出（AI未設定時のフォールバック） ─── */
function extractByRules(text: string): Record<string, unknown> {
  const r: Record<string, unknown> = {};

  // 住所
  const addrMatch = text.match(/(?:所在地?|住所|所在)[：:\s]*([^\n]{5,50})/);
  if (addrMatch) r.address = addrMatch[1].trim();

  // 所有者
  const ownerMatch = text.match(/(?:所有者|登記名義人|権利者)[：:\s]*([^\n]{2,30})/);
  if (ownerMatch) r.owner_name = ownerMatch[1].trim();

  // 面積
  const landMatch = text.match(/(?:土地[面積]*|地積)[：:\s]*([\d,.]+)\s*[㎡m²]/);
  if (landMatch) r.land_area = parseFloat(landMatch[1].replace(/,/g, ""));

  const bldgMatch = text.match(/(?:建物[面積]*|専有面積|延べ?面積|床面積)[：:\s]*([\d,.]+)\s*[㎡m²]/);
  if (bldgMatch) r.building_area = parseFloat(bldgMatch[1].replace(/,/g, ""));

  // 用途地域
  const zoningMatch = text.match(/(第[一二三]種[低中高]層住居専用地域|第[一二]種住居地域|準住居地域|近隣商業地域|商業地域|準工業地域|工業地域|工業専用地域|田園住居地域)/);
  if (zoningMatch) r.zoning = zoningMatch[1];

  // 建ぺい率・容積率
  const bcrMatch = text.match(/建[ぺペ]い率[：:\s]*([\d.]+)\s*[%％]/);
  if (bcrMatch) r.building_coverage_ratio = parseFloat(bcrMatch[1]);

  const farMatch = text.match(/容積率[：:\s]*([\d.]+)\s*[%％]/);
  if (farMatch) r.floor_area_ratio = parseFloat(farMatch[1]);

  // 防火地域
  const fireMatch = text.match(/(準?防火地域)/);
  if (fireMatch) r.fire_zone = fireMatch[1];

  // 道路
  const roadTypeMatch = text.match(/(?:道路[種別]*|接面道路)[：:\s]*([^\n]{2,20})/);
  if (roadTypeMatch) r.road_type = roadTypeMatch[1].trim();

  const roadWidthMatch = text.match(/(?:道路)?幅員[：:\s]*([\d.]+)\s*[mM]/);
  if (roadWidthMatch) r.road_width = parseFloat(roadWidthMatch[1]);

  // インフラ
  if (/(公営水道|上水道)/.test(text)) r.water_supply = "公営水道";
  else if (/井戸/.test(text)) r.water_supply = "井戸水";

  if (/公共下水/.test(text)) r.sewage = "公共下水";
  else if (/浄化槽/.test(text)) r.sewage = "浄化槽";

  if (/都市ガス/.test(text)) r.gas_type = "都市ガス";
  else if (/(LPガス|プロパン)/.test(text)) r.gas_type = "LPガス";

  // 金額
  const priceMatch = text.match(/(?:売買代金|価格|販売価格)[：:\s]*([\d,]+)\s*(?:円|万円)/);
  if (priceMatch) {
    let v = parseInt(priceMatch[1].replace(/,/g, ""), 10);
    if (priceMatch[0].includes("万円")) v *= 10000;
    r.price = v;
  }

  const rentMatch = text.match(/(?:賃料|家賃)[（(]?月額?[）)]?[：:\s]*([\d,]+)\s*円/);
  if (rentMatch) r.rent = parseInt(rentMatch[1].replace(/,/g, ""), 10);

  // 物件種別推定
  if (/マンション|区分所有/.test(text)) r.property_type = "mansion";
  else if (/一戸建|戸建住宅/.test(text)) r.property_type = "house";
  else if (/土地$|宅地/.test(text)) r.property_type = "land";

  // 抵当権
  const mortgageMatch = text.match(/(?:抵当権)[：:\s]*([^\n]{3,80})/);
  if (mortgageMatch) r.mortgage = mortgageMatch[1].trim();

  // 書類種別推定
  if (/登記簿|登記事項/.test(text)) r.document_type = "登記簿謄本";
  else if (/マイソク|物件概要/.test(text)) r.document_type = "マイソク";
  else if (/重要事項説明/.test(text)) r.document_type = "重要事項説明書";
  else if (/賃貸借契約|建物賃貸借/.test(text)) r.document_type = "賃貸契約書";
  else r.document_type = "その他";

  return r;
}

export async function POST(request: NextRequest) {
  try {
    let env: ReturnType<typeof getRequestContext>["env"];
    try {
      env = getRequestContext().env;
    } catch {
      return NextResponse.json(
        { error: "Cloudflare環境外では利用できません。Cloudflare Pagesにデプロイしてください。" },
        { status: 503 }
      );
    }

    const body = await request.json();
    const text = body.text as string;

    if (!text || text.trim().length < 10) {
      return NextResponse.json({ error: "テキストが短すぎます" }, { status: 400 });
    }

    // Workers AI で構造化抽出（AI未設定時はルールベースフォールバック）
    let responseText = "";

    if (env?.AI) {
      const result = await env.AI.run("@cf/meta/llama-3.1-70b-instruct", {
        messages: [
          { role: "system", content: SYSTEM_PROMPT },
          { role: "user", content: USER_PROMPT(text.slice(0, 8000)) },
        ],
        max_tokens: 2000,
        temperature: 0.1,
      }) as { response?: string };
      responseText = result?.response || "";
    } else {
      // AI未設定時: ルールベースで基本フィールドを抽出
      const fallback = extractByRules(text);
      responseText = JSON.stringify(fallback);
    }

    // JSON部分を抽出（```json ... ``` やプレーンJSONに対応）
    let extracted: Record<string, unknown> = {};
    const jsonMatch = responseText.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      try {
        extracted = JSON.parse(jsonMatch[0]);
      } catch {
        return NextResponse.json(
          { error: "AIの応答からJSONを解析できませんでした", raw: responseText },
          { status: 422 }
        );
      }
    } else {
      return NextResponse.json(
        { error: "AIがJSON形式で応答しませんでした", raw: responseText },
        { status: 422 }
      );
    }

    // document_type を分離
    const documentType = extracted.document_type || "その他";
    delete extracted.document_type;

    // 監査ログ（PDF抽出の使用記録）
    try {
      const db = env.DB;
      await ensureSchema(db);
      await writeAuditLog(db, {
        action: "pdf_extract",
        details: `書類種別: ${documentType}, 抽出フィールド数: ${Object.keys(extracted).length}`,
        ip_address: request.headers.get("cf-connecting-ip") || request.headers.get("x-forwarded-for") || undefined,
      });
    } catch { /* ログ失敗は無視 */ }

    return NextResponse.json({
      extracted,
      document_type: documentType,
      field_count: Object.keys(extracted).length,
    });
  } catch (e: unknown) {
    console.error("Extract error:", e);
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "抽出に失敗しました" },
      { status: 500 }
    );
  }
}
