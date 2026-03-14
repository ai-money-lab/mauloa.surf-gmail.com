import { NextRequest, NextResponse } from "next/server";
import { getRequestContext } from "@cloudflare/next-on-pages";
import { getProperty, updatePropertyManual, writeAuditLog } from "@/lib/db/queries";
import { ensureSchema } from "@/lib/db/ensure-schema";

export const runtime = "edge";

function getIp(req: NextRequest): string | undefined {
  return req.headers.get("cf-connecting-ip") || req.headers.get("x-forwarded-for") || undefined;
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { env } = getRequestContext();
  const db = env.DB;
  await ensureSchema(db);

  const property = await getProperty(db, id);
  if (!property) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json(property);
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { env } = getRequestContext();
  const db = env.DB;
  await ensureSchema(db);

  const property = await getProperty(db, id);
  if (!property) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  await db.prepare("DELETE FROM properties WHERE id = ?").bind(id).run();

  // 監査ログ
  try {
    await writeAuditLog(db, {
      property_id: id,
      action: "delete",
      details: `物件削除: ${property.address || id}`,
      ip_address: getIp(req),
    });
  } catch { /* ログ失敗は無視 */ }

  return NextResponse.json({ ok: true });
}

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { env } = getRequestContext();
  const db = env.DB;
  await ensureSchema(db);

  const existing = await getProperty(db, id);
  if (!existing) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  let data: Record<string, unknown>;
  try {
    data = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  // Remove fields that should not be updated directly
  delete data.id;
  delete data.created_at;
  delete data.company_id;
  delete data.created_by;

  // 変更されたフィールドを記録
  const changedFields: string[] = [];
  for (const [key, val] of Object.entries(data)) {
    if (existing[key] !== val) changedFields.push(key);
  }

  try {
    await updatePropertyManual(db, id, data);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("updatePropertyManual failed:", msg);
    return NextResponse.json({ error: `DB更新エラー: ${msg}` }, { status: 500 });
  }

  // 監査ログ
  if (changedFields.length > 0) {
    try {
      await writeAuditLog(db, {
        property_id: id,
        action: "update",
        details: `変更項目: ${changedFields.join(", ")}`,
        ip_address: getIp(req),
      });
    } catch { /* ログ失敗は無視 */ }
  }

  const updated = await getProperty(db, id);
  return NextResponse.json(updated);
}
