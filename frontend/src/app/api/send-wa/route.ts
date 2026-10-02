/**
 * Next.js API Route — WhatsApp Proxy via senderme.my.id
 * API key disimpan di Vercel env (server-side), tidak expose ke browser.
 *
 * Vercel env var yang dibutuhkan:
 *   WA_API_KEY  = wa_key_787f15b9ce664d8fb98a426befba34ca
 *   WA_API_URL  = https://senderme.my.id/api/send-message
 *   WA_OWNER_PHONE = 6281112300343
 */

import { NextRequest, NextResponse } from "next/server";

const WA_API_URL   = process.env.WA_API_URL   || "https://senderme.my.id/api/send-message";
const WA_API_KEY   = process.env.WA_API_KEY   || "";
const OWNER_PHONE  = process.env.WA_OWNER_PHONE || "";

export async function POST(req: NextRequest) {
  try {
    const body: { number?: string; message: string } = await req.json();

    if (!WA_API_KEY) {
      return NextResponse.json(
        { ok: false, detail: "WA_API_KEY not configured in Vercel env" },
        { status: 500 }
      );
    }

    const to = body.number || OWNER_PHONE;
    if (!to) {
      return NextResponse.json(
        { ok: false, detail: "No phone number provided" },
        { status: 400 }
      );
    }

    const resp = await fetch(WA_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": WA_API_KEY,
      },
      body: JSON.stringify({ number: to, message: body.message }),
    });

    const data = await resp.json().catch(() => ({}));
    const ok   = resp.ok && (data.success !== undefined ? Boolean(data.success) : resp.ok);

    return NextResponse.json({
      ok,
      messageId: data.messageId,
      status:    data.status,
      detail:    ok
        ? `messageId=${data.messageId || "?"} status=${data.status || "?"}`
        : JSON.stringify(data),
    });
  } catch (e: any) {
    return NextResponse.json({ ok: false, detail: e.message }, { status: 500 });
  }
}
