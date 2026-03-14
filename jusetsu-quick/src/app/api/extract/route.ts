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

    if (!env?.AI) {
      return NextResponse.json(
        { error: "Workers AIが未設定です。wrangler.tomlの[ai]バインディングを確認してください。" },
        { status: 503 }
      );
    }

    // Workers AI で構造化抽出
    const result = await env.AI.run("@cf/meta/llama-3.1-70b-instruct", {
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: USER_PROMPT(text.slice(0, 8000)) },
      ],
      max_tokens: 2000,
      temperature: 0.1,
    }) as { response?: string };

    const responseText = result?.response || "";

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
