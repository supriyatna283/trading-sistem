"use client";
import { useState, useEffect, useCallback } from "react";
import MainLayout from "@/components/layout/MainLayout";
import { api } from "@/lib/api";

const IMPACT_CONFIG: Record<number, { label: string; color: string; bg: string; icon: string }> = {
  3: { label: "High",    color: "#ef4444", bg: "rgba(239,68,68,0.15)",   icon: "🔴" },
  2: { label: "Medium",  color: "#f59e0b", bg: "rgba(245,158,11,0.15)",  icon: "🟡" },
  1: { label: "Low",     color: "#6b7280", bg: "rgba(107,114,128,0.1)",  icon: "⚪" },
  0: { label: "Holiday", color: "#8b5cf6", bg: "rgba(139,92,246,0.1)",   icon: "🗓️" },
};

function CountdownTimer({ seconds }: { seconds: number }) {
  const [remaining, setRemaining] = useState(seconds);
  useEffect(() => {
    const t = setInterval(() => setRemaining(s => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, []);
  const h = Math.floor(remaining / 3600);
  const m = Math.floor((remaining % 3600) / 60);
  const s = remaining % 60;
  return (
    <span style={{ fontFamily: "monospace", fontWeight: 700, color: "#f59e0b", fontSize: "1.1rem" }}>
      {String(h).padStart(2, "0")}:{String(m).padStart(2, "0")}:{String(s).padStart(2, "0")}
    </span>
  );
}

export default function CalendarPage() {
  const [events, setEvents] = useState<any[]>([]);
  const [nextHigh, setNextHigh] = useState<any>(null);
  const [filter, setFilter] = useState<"ALL" | "HIGH" | "TODAY">("ALL");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (refresh = false) => {
    setLoading(true); setError("");
    try {
      const res = await api.getCalendar();
      setEvents(res.events || []);
      setNextHigh(res.next_high_impact || null);
    } catch (e: any) { setError("Failed to load calendar. " + (e.message || "")); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const displayed = events.filter(e => {
    if (filter === "HIGH") return e.impact_level >= 3;
    if (filter === "TODAY") {
      const today = new Date().toISOString().slice(0, 10);
      return (e.date || "").startsWith(today);
    }
    return true;
  });

  const groupedByDate: Record<string, any[]> = {};
  displayed.forEach(e => {
    const date = (e.date || "").slice(0, 10);
    if (!groupedByDate[date]) groupedByDate[date] = [];
    groupedByDate[date].push(e);
  });

  return (
    <MainLayout>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 800, margin: 0, letterSpacing: "-0.03em" }}>
            Economic Calendar
          </h1>
          <p style={{ color: "var(--text-secondary)", margin: "4px 0 0", fontSize: "0.85rem" }}>
            Avoid trading during high-impact news events
          </p>
        </div>
        <button className="btn-primary" onClick={() => load(true)} disabled={loading}>
          {loading ? "Loading…" : "🔄 Refresh"}
        </button>
      </div>

      {/* Next High-Impact Banner */}
      {nextHigh && (
        <div style={{
          background: "linear-gradient(135deg, rgba(239,68,68,0.15) 0%, rgba(245,158,11,0.1) 100%)",
          border: "1px solid rgba(239,68,68,0.4)", borderRadius: 16, padding: "18px 24px",
          marginBottom: 24, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12,
        }}>
          <div>
            <div style={{ fontSize: "0.75rem", color: "#ef4444", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
              🔴 Next High-Impact Event
            </div>
            <div style={{ fontWeight: 700, fontSize: "1.1rem" }}>{nextHigh.title}</div>
            <div style={{ color: "var(--text-secondary)", fontSize: "0.83rem", marginTop: 3 }}>
              {nextHigh.currency} • {nextHigh.time_formatted}
            </div>
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", textTransform: "uppercase", marginBottom: 4 }}>Countdown</div>
            <CountdownTimer seconds={nextHigh.seconds_until || 0} />
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        {(["ALL", "HIGH", "TODAY"] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            padding: "7px 18px", borderRadius: 8, border: `1px solid ${filter === f ? "var(--accent)" : "var(--border)"}`,
            background: filter === f ? "rgba(139,92,246,0.15)" : "transparent",
            color: filter === f ? "var(--accent)" : "var(--text-secondary)",
            cursor: "pointer", fontWeight: 600, fontSize: "0.83rem", transition: "all 0.2s",
          }}>
            {f === "ALL" ? "All Events" : f === "HIGH" ? "🔴 High Impact" : "📅 Today"}
          </button>
        ))}
        <div style={{ marginLeft: "auto", color: "var(--text-secondary)", fontSize: "0.82rem", alignSelf: "center" }}>
          {displayed.length} events
        </div>
      </div>

      {error && (
        <div style={{ padding: 16, borderRadius: 12, background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", marginBottom: 20 }}>
          ⚠️ {error}
        </div>
      )}

      {loading && events.length === 0 && (
        <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-secondary)" }}>Loading events…</div>
      )}

      {/* Event Groups by Date */}
      {Object.entries(groupedByDate).map(([date, dayEvents]) => (
        <div key={date} style={{ marginBottom: 28 }}>
          <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase",
            letterSpacing: "0.08em", marginBottom: 10, borderBottom: "1px solid var(--border)", paddingBottom: 8 }}>
            {date ? new Date(date + "T00:00:00").toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" }) : "Unknown Date"}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {dayEvents.map((event: any, i: number) => {
              const cfg = IMPACT_CONFIG[event.impact_level] || IMPACT_CONFIG[1];
              return (
                <div key={event.id || i} style={{
                  background: "var(--card-bg)", border: `1px solid var(--border)`,
                  borderLeft: `4px solid ${cfg.color}`, borderRadius: 12, padding: "14px 18px",
                  display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap",
                  transition: "border-color 0.2s",
                }}>
                  <div style={{ minWidth: 90, fontSize: "0.82rem", color: "var(--text-secondary)", fontFamily: "monospace" }}>
                    {event.time_formatted?.split(" ")[1] || "All Day"}
                  </div>
                  <div style={{
                    padding: "2px 10px", borderRadius: 6, background: cfg.bg, fontSize: "0.73rem",
                    fontWeight: 700, color: cfg.color, whiteSpace: "nowrap",
                  }}>
                    {cfg.icon} {cfg.label}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{event.title}</div>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: 2 }}>
                      {event.currency}
                      {event.forecast && <span> · Forecast: <strong>{event.forecast}</strong></span>}
                      {event.previous && <span> · Previous: {event.previous}</span>}
                      {event.actual && <span style={{ color: "#10b981", fontWeight: 700 }}> · Actual: {event.actual}</span>}
                    </div>
                  </div>
                  {!event.relevant_to_crypto && (
                    <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", opacity: 0.6 }}>
                      {event.currency}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {!loading && displayed.length === 0 && (
        <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-secondary)" }}>
          No events found for this filter.
        </div>
      )}
    </MainLayout>
  );
}
