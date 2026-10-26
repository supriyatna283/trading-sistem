/**
 * Next.js API Route — WhatsApp Proxy via senderme.my.id
 * API key dan nomor tujuan disimpan di Vercel env (server-side), tidak expose ke browser.
 *
 * Vercel env vars yang dibutuhkan:
 *   WA_API_URL    = https://senderme.my.id/api/send-message
 *   WA_API_KEY    = (secret, server-side only)
 *   WA_OWNER_PHONE = (nomor tujuan)
 *   WA_TOKEN      = (opsional) shared token untuk membatasi akses endpoint ini
 */

import { NextRequest, NextResponse } from "next/server";

const WA_API_URL   = process.env.WA_API_URL   || "https://senderme.my.id/api/send-message";
const WA_API_KEY   = process.env.WA_API_KEY   || "";
const OWNER_PHONE  = process.env.WA_OWNER_PHONE || "";
const WA_TOKEN     = process.env.WA_TOKEN      || "";

// In-memory rate limit (per process). Untuk deploy multi-instance, ganti ke Redis/Upstash.
const hits = new Map<string, number[]>();
const WINDOW_MS = 60_000;
const MAX_PER_WINDOW = 10;

export async function POST(req: NextRequest) {
  try {
    // 1. Optional shared token — when configured, reject callers without it.
    if (WA_TOKEN) {
      const auth = req.headers.get("x-wa-token") || req.headers.get("authorization");
      if (auth !== `Bearer ${WA_TOKEN}` && auth !== WA_TOKEN) {
        return NextResponse.json({ ok: false, detail: "Unauthorized" }, { status: 401 });
      }
    }

    const body: { number?: string; message?: string } = await req.json().catch(() => ({}));
    if (!body.message || typeof body.message !== "string") {
      return NextResponse.json({ ok: false, detail: "Missing message" }, { status: 400 });
    }

    if (!WA_API_KEY) {
      return NextResponse.json(
        { ok: false, detail: "WA_API_KEY not configured in Vercel env" },
        { status: 500 }
      );
    }

    // 2. Default to the owner's phone; an explicit number is allowed only for the
    //    "Kirim Test" flow and must look like a phone number.
    const to = String(body.number || OWNER_PHONE).trim();
    if (!to) {
      return NextResponse.json(
        { ok: false, detail: "No phone number provided" },
        { status: 400 }
      );
    }
    if (!/^\+?\d{6,20}$/.test(to)) {
      return NextResponse.json(
        { ok: false, detail: "Invalid phone number" },
        { status: 400 }
      );
    }

    // 3. Basic rate limit to prevent abuse.
    const now = Date.now();
    const recent = (hits.get("wa") || []).filter((t) => now - t < WINDOW_MS);
    if (recent.length >= MAX_PER_WINDOW) {
      return NextResponse.json({ ok: false, detail: "Rate limit exceeded" }, { status: 429 });
    }
    recent.push(now);
    hits.set("wa", recent);

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
