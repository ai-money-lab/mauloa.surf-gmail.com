import { NextRequest, NextResponse } from "next/server";
import { geocode } from "@/lib/api/geocode";

export const runtime = "edge";

export async function POST(req: NextRequest) {
  const { address } = await req.json();
  if (!address) {
    return NextResponse.json({ error: "address is required" }, { status: 400 });
  }
  const result = await geocode(address);
  if (!result) {
    return NextResponse.json({ error: "geocode failed" }, { status: 404 });
  }
  return NextResponse.json(result);
}
