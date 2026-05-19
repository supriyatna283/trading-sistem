"use client";

import { useEffect, useState } from "react";
import { checkApiHealth } from "@/lib/api";

export function notifyApiError(message: string) {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("api-error", { detail: message }));
  }
}

export default function ApiStatusBanner() {
  const [online, setOnline] = useState<boolean | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const ping = async () => {
      const ok = await checkApiHealth();
      if (!cancelled) setOnline(ok);
    };

    ping();
    const id = setInterval(ping, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    const onError = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail;
      if (detail) setMessage(detail);
    };
    window.addEventListener("api-error", onError);
    return () => window.removeEventListener("api-error", onError);
  }, []);

  if (online === null) return null;
  if (online && !message) return null;

  const isOffline = !online;
  const text = isOffline
    ? `Backend API tidak terjangkau. Pastikan server berjalan di ${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}`
    : message;

  return (
    <div
      role="alert"
      style={{
        marginBottom: 16,
        padding: "12px 16px",
        borderRadius: 10,
        fontSize: "0.82rem",
        fontWeight: 600,
        background: isOffline ? "rgba(239,68,68,0.12)" : "rgba(245,158,11,0.12)",
        border: `1px solid ${isOffline ? "rgba(239,68,68,0.35)" : "rgba(245,158,11,0.35)"}`,
        color: isOffline ? "#fca5a5" : "#fcd34d",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 12,
      }}
    >
      <span>{text}</span>
      {!isOffline && message && (
        <button
          type="button"
          onClick={() => setMessage(null)}
          style={{
            background: "transparent",
            border: "none",
            color: "inherit",
            cursor: "pointer",
            fontSize: "1rem",
            lineHeight: 1,
          }}
          aria-label="Dismiss"
        >
          ×
        </button>
      )}
    </div>
  );
}
