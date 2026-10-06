"use client";

import { useMemo } from "react";

interface FibData {
  levels: { label: string; price: number; isKey: boolean; isExtension: boolean; isGolden: boolean }[];
  direction: "UP" | "DOWN";
  swingHigh: number;
  swingLow: number;
}

interface Props {
  symbol: string;
  currentPrice: number | null;
  fibData: FibData | null;
  adr?: number;
}

const KILL_ZONES = [
  { name: "Asia",          start:  0, end:  3, color: "#f59e0b", emoji: "??" },
  { name: "London",        start:  7, end: 10, color: "#60a5fa", emoji: "????" },
  { name: "NY Open",       start: 12, end: 15, color: "#34d399", emoji: "??" },
  { name: "NY Power Hour", start: 15, end: 17, color: "#a78bfa", emoji: "?" },
] as const;

const DOW_BIAS = [
  { day: 0, name: "Sun", bias: "—",        color: "rgba(255,255,255,0.3)", note: "Closed" },
  { day: 1, name: "Mon", bias: "Reversal", color: "#f59e0b",               note: "SMC range set / turtle soup" },
  { day: 2, name: "Tue", bias: "Trend",    color: "#34d399",               note: "Expansion day — best entries" },
  { day: 3, name: "Wed", bias: "Trend",    color: "#34d399",               note: "Continuation or mid-week reversal" },
  { day: 4, name: "Thu", bias: "Reversal", color: "#f87171",               note: "London sets high/low, NY reverses" },
  { day: 5, name: "Fri", bias: "Close",    color: "#a78bfa",               note: "Profit taking / position close" },
  { day: 6, name: "Sat", bias: "—",        color: "rgba(255,255,255,0.3)", note: "Closed" },
] as const;

function getNowUTC() {
  const now = new Date();
  return {
    utcHour: now.getUTCHours(),
    utcDay:  now.getUTCDay(),
    utcTimeStr: now.toUTCString().slice(17, 22) + " UTC",
  };
}

function getKillZoneStatus(utcHour: number) {
  const active = KILL_ZONES.filter(kz => utcHour >= kz.start && utcHour < kz.end);
  const next   = KILL_ZONES.find(kz => kz.start > utcHour);
  return { active, next };
}

function getPremiumDiscount(currentPrice: number, fibData: FibData) {
  const range = fibData.swingHigh - fibData.swingLow;
  if (range <= 0) return { zone: "Equilibrium" as const, pct: 50, color: "#facc15" };
  const posFromLow = ((currentPrice - fibData.swingLow) / range) * 100;
  const pct = Math.max(0, Math.min(100, posFromLow));
  if (pct > 55) return { zone: "Premium"      as const, pct, color: "#f87171" };
  if (pct < 45) return { zone: "Discount"     as const, pct, color: "#34d399" };
  return               { zone: "Equilibrium"  as const, pct, color: "#facc15" };
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{
        fontSize: "0.6rem", fontWeight: 800, letterSpacing: "0.1em",
        color: "var(--text-muted)", textTransform: "uppercase" as const,
        borderBottom: "1px solid rgba(255,255,255,0.04)", paddingBottom: 4,
      }}>{title}</div>
      {children}
    </div>
  );
}

export default function ICTContextPanel({ symbol: _symbol, currentPrice, fibData, adr }: Props) {
  const { utcHour, utcDay, utcTimeStr } = useMemo(getNowUTC, []);
  const { active: activeKZs, next: nextKZ } = useMemo(() => getKillZoneStatus(utcHour), [utcHour]);
  const dowInfo = DOW_BIAS[utcDay];

  const pd = useMemo(() => {
    if (!currentPrice || !fibData) return null;
    return getPremiumDiscount(currentPrice, fibData);
  }, [currentPrice, fibData]);

  return (
    <div style={{
      background: "rgba(255,255,255,0.02)",
      border: "1px solid var(--border)",
      borderRadius: 10, padding: "12px 14px",
      display: "flex", flexDirection: "column", gap: 10,
      fontSize: "0.72rem", fontFamily: "'Inter', sans-serif",
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontWeight: 800, color: "var(--text-primary)", fontSize: "0.78rem" }}>
          ?? ICT Context
        </span>
        <span style={{ color: "var(--text-muted)", fontSize: "0.62rem", fontFamily: "'JetBrains Mono', monospace" }}>
          {utcTimeStr}
        </span>
      </div>

      <Section title="Kill Zones">
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {KILL_ZONES.map(kz => {
            const isActive = utcHour >= kz.start && utcHour < kz.end;
            return (
              <div key={kz.name} style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "4px 8px", borderRadius: 6,
                background: isActive ? `${kz.color}14` : "transparent",
                border: isActive ? `1px solid ${kz.color}40` : "1px solid transparent",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <span style={{ fontSize: "0.85rem" }}>{kz.emoji}</span>
                  <span style={{ color: isActive ? kz.color : "var(--text-muted)", fontWeight: isActive ? 800 : 400 }}>
                    {kz.name}
                  </span>
                  {isActive && (
                    <span style={{
                      background: `${kz.color}25`, color: kz.color,
                      fontSize: "0.55rem", fontWeight: 800, padding: "1px 5px",
                      borderRadius: 10, letterSpacing: "0.08em",
                    }}>LIVE</span>
                  )}
                </div>
                <span style={{ color: "var(--text-muted)", fontSize: "0.6rem", fontFamily: "'JetBrains Mono', monospace" }}>
                  {String(kz.start).padStart(2,"0")}–{String(kz.end).padStart(2,"0")} UTC
                </span>
              </div>
            );
          })}
          {activeKZs.length === 0 && (
            <div style={{ color: "var(--text-muted)", fontSize: "0.63rem", textAlign: "center", marginTop: 2 }}>
              {nextKZ
                ? <>Next: <span style={{ color: nextKZ.color }}>{nextKZ.emoji} {nextKZ.name}</span> @ {String(nextKZ.start).padStart(2,"0")}:00 UTC</>
                : "No more Kill Zones today · Next: Asia 00:00 UTC"}
            </div>
          )}
        </div>
      </Section>

      <Section title="Premium / Discount">
        {pd ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{
                color: pd.color, fontWeight: 800, fontSize: "0.77rem",
                background: `${pd.color}15`, border: `1px solid ${pd.color}40`,
                borderRadius: 6, padding: "2px 10px",
              }}>
                {pd.zone === "Premium" ? "?? Premium · Short Bias"
                  : pd.zone === "Discount" ? "?? Discount · Long Bias"
                  : "?? Equilibrium"}
              </span>
              <span style={{ color: pd.color, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700 }}>
                {pd.pct.toFixed(1)}%
              </span>
            </div>
            <div style={{ position: "relative", height: 6, borderRadius: 3, overflow: "hidden", background: "rgba(255,255,255,0.06)" }}>
              <div style={{ position: "absolute", left: "45%", width: "10%", height: "100%", background: "rgba(250,204,21,0.18)" }} />
              <div style={{
                position: "absolute", left: `${Math.max(0, Math.min(96, pd.pct))}%`,
                width: "4%", height: "100%", background: pd.color, borderRadius: 3,
              }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-muted)", fontSize: "0.57rem" }}>
              <span>Low (0%)</span><span style={{ color: "#facc15" }}>EQ 50%</span><span>High (100%)</span>
            </div>
            <div style={{ color: "var(--text-muted)", fontSize: "0.62rem" }}>
              {pd.zone === "Premium" ? "Seek shorts from OB/FVG in premium. Avoid longs."
                : pd.zone === "Discount" ? "Seek longs from OB/FVG in discount. Avoid shorts."
                : "At equilibrium — wait for expansion or HTF bias."}
            </div>
          </div>
        ) : (
          <span style={{ color: "var(--text-muted)", fontSize: "0.65rem" }}>
            Enable FIB overlay to see Premium/Discount
          </span>
        )}
      </Section>

      <Section title="Day-of-Week Tendency">
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{
              color: dowInfo.color, fontWeight: 800, fontSize: "0.77rem",
              background: `${dowInfo.color}15`, border: `1px solid ${dowInfo.color}35`,
              borderRadius: 6, padding: "2px 10px",
            }}>{dowInfo.name} · {dowInfo.bias}</span>
          </div>
          <div style={{ color: "var(--text-muted)", fontSize: "0.62rem" }}>{dowInfo.note}</div>
          <div style={{ display: "flex", gap: 3, marginTop: 3 }}>
            {DOW_BIAS.slice(1, 6).map(d => (
              <div key={d.day} style={{
                flex: 1, height: 4, borderRadius: 2,
                background: d.day === utcDay ? d.color : "rgba(255,255,255,0.08)",
              }} />
            ))}
          </div>
          <div style={{ display: "flex", gap: 3 }}>
            {["M","T","W","T","F"].map((d, i) => (
              <span key={i} style={{
                flex: 1, textAlign: "center" as const, fontSize: "0.55rem",
                color: (i + 1) === utcDay ? "var(--text-primary)" : "var(--text-muted)",
                fontWeight: (i + 1) === utcDay ? 800 : 400,
              }}>{d}</span>
            ))}
          </div>
        </div>
      </Section>

      {adr !== undefined && adr > 0 && (
        <Section title="ADR Consumed">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ flex: 1, height: 6, borderRadius: 3, overflow: "hidden", background: "rgba(255,255,255,0.06)" }}>
              <div style={{
                width: `${Math.min(100, adr)}%`, height: "100%",
                background: adr > 80 ? "#ef4444" : adr > 50 ? "#f59e0b" : "#22c55e",
                borderRadius: 3, transition: "width 0.5s",
              }} />
            </div>
            <span style={{
              color: adr > 80 ? "#ef4444" : adr > 50 ? "#f59e0b" : "#22c55e",
              fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", fontSize: "0.73rem",
            }}>{adr.toFixed(1)}%</span>
            <span style={{ color: "var(--text-muted)", fontSize: "0.6rem" }}>
              {adr > 80 ? "extended" : adr > 50 ? "halfway" : "early"}
            </span>
          </div>
        </Section>
      )}
    </div>
  );
}
