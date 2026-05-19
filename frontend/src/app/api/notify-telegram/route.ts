/**
 * Telegram Notification Proxy
 * HuggingFace blocks outbound HTTPS to api.telegram.org.
 * This Vercel route acts as a relay: HuggingFace → Vercel → Telegram.
 */
import { NextRequest, NextResponse } from "next/server";

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || "";
const CHAT_ID = process.env.TELEGRAM_CHAT_ID || "";

export async function POST(req: NextRequest) {
  // Validate shared secret to prevent unauthorized use
  const secret = req.headers.get("x-proxy-secret");
  const expectedSecret = process.env.PROXY_SECRET;
  if (!expectedSecret) {
    return NextResponse.json({ error: "PROXY_SECRET not configured" }, { status: 503 });
  }
  if (secret !== expectedSecret) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (!BOT_TOKEN || !CHAT_ID) {
    return NextResponse.json({ error: "Telegram credentials not configured" }, { status: 500 });
  }

  let body: { text?: string; parse_mode?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const text = body.text || "";
  const parse_mode = body.parse_mode || "HTML";

  if (!text) {
    return NextResponse.json({ error: "text is required" }, { status: 400 });
  }

  try {
    const resp = await fetch(
      `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: CHAT_ID,
          text,
          parse_mode,
          disable_web_page_preview: true,
        }),
      }
    );

    const result = await resp.json();
    if (result.ok) {
      return NextResponse.json({ success: true });
    } else {
      return NextResponse.json({ success: false, telegram_error: result }, { status: 502 });
    }
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

// Health check
export async function GET() {
  return NextResponse.json({
    status: "Telegram proxy active",
    credentials: { token: !!BOT_TOKEN, chat_id: !!CHAT_ID },
  });
}
