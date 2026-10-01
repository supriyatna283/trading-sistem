"use client";

import { useState, useEffect, useCallback } from "react";
import { API_URL } from "@/lib/utils";

interface KillzoneData {
  current_session: string;
  current_kz: { name: string; start: number; end: number; color: string; desc: string } | null;
  next_kz: { name: string; start: number; end: number; color: string; desc: string } | null;
  time_to_next: string;
  mins_to_next: number;
  is_high_volume_kz: boolean;
  is_killzone_active: boolean;
  utc_time: string;
  trade_advice: string;
  all_sessions: Array<{ name: string; start: number; end: number; color: string; desc: string }>;
}

const SESSION_ICONS: Record<string, string> = {
  ASIA:         "🌏",
  LONDON_OPEN:  "🇬🇧",
  LONDON:       "🏙️",
  NY_OPEN:      "🗽",
  NY_AM:        "📈",
  NY_LUNCH:     "🍔",
  NY_PM:        "🌅",
  DEAD_ZONE:    "😴",
};

function SessionBar({ sessions, currentSession }: { sessions: KillzoneData["all_sessions"]; currentSession: string }) {
  const totalHours = 24;
  return (
    <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", background: "rgba(255,255,255,0.05)", marginTop: 12 }}>
      {sessions.map((s) => {
        const widthPct = ((s.end - s.start) / totalHours) * 100;
        const isActive = s.name === currentSession;
        return (
          <div
            key={s.name}
            title={`${s.name}: ${s.start}:00–${s.end}:00 UTC`}
            style={{
              width: `${widthPct}%`,
              background: isActive ? s.color : `${s.color}30`,
              transition: "all 0.3s",
              borderRight: "1px solid rgba(0,0,0,0.4)",
              boxShadow: isActive ? `0 0 8px ${s.color}80` : "none",
              position: "relative",
            }}
          />
        );
      })}
    </div>
  );
}

export function KillzoneTimer({ compact = false }: { compact?: boolean }) {
  const [data, setData]       = useState<KillzoneData | null>(null);
  const [displayTime, setDisplayTime] = useState("");

  const fetchKZ = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/pro/killzones`);
      if (res.ok) setData(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchKZ();
    const interval = setInterval(fetchKZ, 30_000); // refresh every 30s
    return () => clearInterval(interval);
  }, [fetchKZ]);

  // Real-time UTC clock
  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setDisplayTime(
        now.toUTCString().split(" ")[4] + " UTC"
      );
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);

  if (!data) {
    return (
      <div style={{ height: 80, background: "rgba(255,255,255,0.02)", borderRadius: 12, border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="skeleton" style={{ width: 120, height: 16 }} />
      </div>
    );
  }

  const kz    = data.current_kz;
  const color = kz?.color ?? "#64748b";
  const icon  = SESSION_ICONS[data.current_session] ?? "⏰";

  if (compact) {
    return (
      <div
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "6px 12px", borderRadius: 10,
          background: data.is_killzone_active ? `${color}15` : "rgba(255,255,255,0.03)",
          border: `1px solid ${data.is_killzone_active ? color + "50" : "rgba(255,255,255,0.06)"}`,
          boxShadow: data.is_killzone_active ? `0 0 16px ${color}20` : "none",
          transition: "all 0.3s",
        }}
      >
        {data.is_killzone_active && (
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: color, boxShadow: `0 0 6px ${color}` }}
            className="animate-pulse-dot" />
        )}
        <span style={{ fontSize: "0.7rem", fontWeight: 700, color: data.is_killzone_active ? color : "var(--text-muted)" }}>
          {icon} {kz?.name?.replace("_", " ") ?? data.current_session}
        </span>
        <span style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
          {displayTime}
        </span>
        <span style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>
          Next: {data.time_to_next}
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        padding: 20,
        borderRadius: 16,
        background: "rgba(255,255,255,0.02)",
        border: `1px solid ${data.is_killzone_active ? color + "40" : "rgba(255,255,255,0.06)"}`,
        boxShadow: data.is_killzone_active ? `0 0 30px ${color}15, inset 0 1px 0 ${color}10` : "none",
        transition: "all 0.5s ease",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Ambient glow when active */}
      {data.is_killzone_active && (
        <div style={{
          position: "absolute", inset: 0, pointerEvents: "none",
          background: `radial-gradient(ellipse at 50% 0%, ${color}10 0%, transparent 70%)`,
        }} />
      )}

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, position: "relative" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            {data.is_killzone_active && (
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: color, boxShadow: `0 0 8px ${color}` }}
                className="animate-pulse-dot" />
            )}
            <span style={{ fontSize: "0.65rem", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.12em", color: "var(--text-muted)" }}>
              ICT Killzone
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: "1.6rem", lineHeight: 1 }}>{icon}</span>
            <div>
              <div style={{ fontSize: "1rem", fontWeight: 800, color: data.is_killzone_active ? color : "#fff" }}>
                {(kz?.name ?? data.current_session).replace(/_/g, " ")}
              </div>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 1 }}>{kz?.desc ?? "Market session"}</div>
            </div>
          </div>
        </div>

        {/* UTC Clock */}
        <div style={{ textAlign: "right" }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "1rem", fontWeight: 700, color: "#3b82f6", letterSpacing: "0.05em" }}>
            {displayTime}
          </div>
          <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginTop: 2 }}>
            Next KZ in <span style={{ color, fontWeight: 700 }}>{data.time_to_next}</span>
          </div>
        </div>
      </div>

      {/* Next KZ */}
      {data.next_kz && (
        <div style={{
          display: "flex", alignItems: "center", gap: 8, padding: "8px 12px",
          borderRadius: 8, background: `${data.next_kz.color}10`,
          border: `1px solid ${data.next_kz.color}20`, marginBottom: 14,
        }}>
          <span style={{ fontSize: "0.9rem" }}>{SESSION_ICONS[data.next_kz.name] ?? "⏰"}</span>
          <div>
            <span style={{ fontSize: "0.72rem", fontWeight: 700, color: data.next_kz.color }}>
              Next: {data.next_kz.name.replace(/_/g, " ")}
            </span>
            <span style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginLeft: 8 }}>
              {data.next_kz.desc}
            </span>
          </div>
        </div>
      )}

      {/* 24h Session Bar */}
      <SessionBar sessions={data.all_sessions} currentSession={data.current_session} />
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
        <span style={{ fontSize: "0.55rem", color: "var(--text-muted)" }}>00:00 UTC</span>
        <span style={{ fontSize: "0.55rem", color: "var(--text-muted)" }}>12:00 UTC</span>
        <span style={{ fontSize: "0.55rem", color: "var(--text-muted)" }}>24:00 UTC</span>
      </div>

      {/* Trade advice badge */}
      <div style={{
        marginTop: 14, padding: "8px 14px", borderRadius: 8,
        background: data.is_killzone_active ? `${color}15` : "rgba(255,255,255,0.03)",
        border: `1px solid ${data.is_killzone_active ? color + "30" : "rgba(255,255,255,0.06)"}`,
        fontSize: "0.75rem", fontWeight: 700,
        color: data.is_killzone_active ? color : "var(--text-muted)",
      }}>
        {data.trade_advice}
      </div>
    </div>
  );
}
