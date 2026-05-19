import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { token, chat_id, text, parse_mode, disable_web_page_preview } = body;

    if (!token || !chat_id || !text) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 400 });
    }

    const url = `https://api.telegram.org/bot${token}/sendMessage`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id,
        text,
        parse_mode: parse_mode || "HTML",
        disable_web_page_preview: disable_web_page_preview !== undefined ? disable_web_page_preview : true,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json({ error: data.description || "Telegram API error" }, { status: response.status });
    }

    return NextResponse.json({ success: true, data });
  } catch (error: any) {
    console.error("Telegram Relay Error:", error);
    return NextResponse.json({ error: error.message || "Internal server error" }, { status: 500 });
  }
}
