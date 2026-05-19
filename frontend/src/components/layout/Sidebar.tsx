"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { 
  LayoutDashboard, 
  Search, 
  Target, 
  LineChart, 
  Globe, 
  Brain, 
  Activity, 
  Layers, 
  FlaskConical, 
  Shield, 
  Wallet, 
  BookOpen, 
  Bell, 
  Calendar, 
  Puzzle,
  ChevronLeft,
  ChevronRight,
  Zap
} from "lucide-react";

const NAV_GROUPS = [
  {
    label: "Core",
    items: [
      { href: "/",            label: "Dashboard",   icon: LayoutDashboard, color: "#3b82f6" },
      { href: "/scanner",     label: "Scanner",     icon: Search,          color: "#8b5cf6" },
      { href: "/setups",      label: "Setups",      icon: Target,          color: "#f43f5e" },
      { href: "/charts",      label: "Charts",      icon: LineChart,       color: "#0ea5e9" },
      { href: "/sentiment",   label: "Sentiment",   icon: Globe,           color: "#10b981" },
      { href: "/market-intel",label: "Market Intel",icon: Brain,           color: "#f59e0b" },
    ],
  },
  {
    label: "Tools",
    items: [
      { href: "/smart-tape",  label: "Smart Tape",  icon: Activity,        color: "#ec4899" },
      { href: "/mtf",         label: "MTF Confirm", icon: Layers,          color: "#6366f1" },
      { href: "/backtest",    label: "Backtest",    icon: FlaskConical,    color: "#14b8a6" },
      { href: "/risk",        label: "Risk",        icon: Shield,          color: "#ef4444" },
      { href: "/portfolio",   label: "Portfolio",   icon: Wallet,          color: "#22c55e" },
      { href: "/journal",     label: "Journal",     icon: BookOpen,        color: "#f97316" },
      { href: "/alerts",      label: "Alerts",      icon: Bell,            color: "#eab308" },
      { href: "/calendar",    label: "Calendar",    icon: Calendar,        color: "#a855f7" },
      { href: "/strategy",    label: "Strategy",    icon: Puzzle,          color: "#06b6d4" },
    ],
  },
];

const EXCHANGES = [
  { name: "Bybit", color: "#f7931a", status: "live" },
  { name: "OKX", color: "#00b4ff", status: "live" },
  { name: "Binance", color: "#f0b90b", status: "data" },
];

export default function Sidebar({ onWidthChange }: { onWidthChange?: (w: number) => void }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [time, setTime] = useState("");

  const handleCollapse = (val: boolean) => {
    setCollapsed(val);
    onWidthChange?.(val ? 68 : 228);
  };

  useEffect(() => {
    const tick = () =>
      setTime(new Date().toLocaleTimeString("en-US", { hour12: false }));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);

  const w = collapsed ? 68 : 228;

  return (
    <aside
      style={{
        width: w,
        minHeight: "100vh",
        background: "rgba(8, 12, 20, 0.92)",
        backdropFilter: "blur(20px)",
        borderRight: "1px solid rgba(255, 255, 255, 0.05)",
        display: "flex",
        flexDirection: "column",
        position: "fixed",
        top: 0,
        left: 0,
        zIndex: 50,
        transition: "width 0.3s cubic-bezier(.4,0,.2,1)",
        overflow: "hidden",
        boxShadow: "10px 0 30px rgba(0,0,0,0.5)",
      }}
    >
      {/* ── Logo ── */}
      <div
        style={{
          padding: collapsed ? "20px 0" : "20px 16px",
          borderBottom: "1px solid #1e2a3d",
          display: "flex",
          alignItems: "center",
          justifyContent: collapsed ? "center" : "space-between",
          minHeight: 72,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 12,
                background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                position: "relative",
                boxShadow: "0 0 20px rgba(59,130,246,0.4)",
                border: "1px solid rgba(255,255,255,0.1)",
              }}
            >
              <Zap size={20} fill="#fff" color="#fff" style={{ filter: "drop-shadow(0 0 8px rgba(255,255,255,0.8))" }} />
              <div 
                style={{
                  position: "absolute",
                  inset: -2,
                  borderRadius: 14,
                  border: "1px solid rgba(59,130,246,0.3)",
                  opacity: 0.5,
                }}
              />
            </div>
          {!collapsed && (
            <div>
              <div
                style={{
                  fontFamily: "'Outfit', sans-serif",
                  fontWeight: 800,
                  fontSize: "0.95rem",
                  letterSpacing: "-0.03em",
                  background: "linear-gradient(135deg, #e2e8f0, #94a3b8)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                TradeIntel
              </div>
              <div
                style={{
                  fontSize: "0.58rem",
                  color: "#3b82f6",
                  fontWeight: 700,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                }}
              >
                Multi-Exchange
              </div>
            </div>
          )}
        </div>
        {!collapsed && (
          <button
            onClick={() => handleCollapse(true)}
            style={{
              background: "rgba(255,255,255,0.04)",
              border: "1px solid #1e2a3d",
              borderRadius: 6,
              color: "#4a5568",
              width: 24,
              height: 24,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 12,
              transition: "all 0.15s",
              flexShrink: 0,
            }}
            title="Collapse sidebar"
          >
            <ChevronLeft size={14} />
          </button>
        )}
        {collapsed && (
          <button
            onClick={() => handleCollapse(false)}
            style={{
              position: "absolute",
              top: 24,
              right: -1,
              background: "#0b0f1c",
              border: "1px solid #1e2a3d",
              borderRadius: "0 6px 6px 0",
              color: "#3b82f6",
              width: 16,
              height: 28,
              cursor: "pointer",
              fontSize: 10,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <ChevronRight size={12} />
          </button>
        )}
      </div>

      {/* ── Navigation ── */}
      <nav style={{ flex: 1, overflowY: "auto", padding: "12px 8px" }}>
        {NAV_GROUPS.map((group) => (
          <div key={group.label} style={{ marginBottom: 8 }}>
            {!collapsed && (
              <div
                className="no-scrollbar"
                style={{
                  fontSize: "0.65rem",
                  fontWeight: 800,
                  color: "#475569",
                  textTransform: "uppercase",
                  letterSpacing: "0.15em",
                  padding: "16px 12px 8px",
                }}
              >
                {group.label}
              </div>
            )}
            {group.items.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  title={collapsed ? item.label : undefined}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: collapsed ? "9px" : "9px 12px",
                    marginBottom: 2,
                    color: isActive ? "#f8fafc" : "#94a3b8",
                    fontWeight: isActive ? 600 : 500,
                    fontSize: "0.85rem",
                    textDecoration: "none",
                    transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                    justifyContent: collapsed ? "center" : "flex-start",
                    background: isActive
                      ? "rgba(255,255,255,0.03)"
                      : "transparent",
                    border: "1px solid transparent",
                    borderLeft: isActive ? `2px solid ${item.color}` : "2px solid transparent",
                    borderRadius: collapsed ? 10 : "0 10px 10px 0",
                    marginLeft: collapsed ? 0 : -8,
                    paddingLeft: collapsed ? 9 : 18,
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      (e.currentTarget as HTMLElement).style.background =
                        "rgba(255,255,255,0.03)";
                      (e.currentTarget as HTMLElement).style.color = "#e2e8f0";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      (e.currentTarget as HTMLElement).style.background = "transparent";
                      (e.currentTarget as HTMLElement).style.color = "#8494b0";
                    }
                  }}
                >
                  <div
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: 8,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      background: isActive 
                        ? `${item.color}25`
                        : "rgba(255,255,255,0.03)",
                      border: `1px solid ${isActive ? `${item.color}40` : "transparent"}`,
                      color: isActive ? item.color : "#64748b",
                      transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                      flexShrink: 0,
                      boxShadow: isActive ? `0 0 12px ${item.color}20` : "none",
                    }}
                  >
                    <item.icon 
                      size={collapsed ? 17 : 16} 
                      strokeWidth={isActive ? 2.5 : 2}
                      style={{
                        transition: "transform 0.2s cubic-bezier(.34,1.56,.64,1)",
                        transform: isActive ? "scale(1.1)" : "scale(1)",
                      }}
                    />
                  </div>
                  {!collapsed && (
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {item.label}
                    </span>
                  )}
                  {!collapsed && isActive && (
                    <div
                      style={{
                        marginLeft: "auto",
                        width: 5,
                        height: 5,
                        borderRadius: "50%",
                        background: "#3b82f6",
                        boxShadow: "0 0 6px #3b82f6",
                        flexShrink: 0,
                      }}
                    />
                  )}
                </Link>
              );
            })}
            {!collapsed && group.label === "Core" && (
              <div style={{ height: 1, background: "linear-gradient(90deg, transparent, #1e2a3d, transparent)", margin: "8px 4px" }} />
            )}
          </div>
        ))}
      </nav>

      {/* ── Exchange Status ── */}
      {!collapsed && (
        <div
          style={{
            padding: "12px 14px",
            borderTop: "1px solid #1e2a3d",
            background: "rgba(0,0,0,0.2)",
          }}
        >
          <div
            style={{
              fontSize: "0.58rem",
              fontWeight: 700,
              color: "#2e3f5c",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              marginBottom: 8,
            }}
          >
            Exchange Feed
          </div>
          {EXCHANGES.map((ex) => (
            <div
              key={ex.name}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 5,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div
                  className="animate-pulse-dot"
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    background: ex.color,
                    boxShadow: `0 0 5px ${ex.color}`,
                    flexShrink: 0,
                  }}
                />
                <span style={{ fontSize: "0.72rem", color: "#8494b0", fontWeight: 500 }}>
                  {ex.name}
                </span>
              </div>
              <span
                style={{
                  fontSize: "0.6rem",
                  fontWeight: 700,
                  color: ex.color,
                  background: `${ex.color}15`,
                  padding: "1px 6px",
                  borderRadius: 4,
                }}
              >
                LIVE
              </span>
            </div>
          ))}

          {/* Clock */}
          <div
            style={{
              marginTop: 10,
              paddingTop: 10,
              borderTop: "1px solid #1e2a3d",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span style={{ fontSize: "0.65rem", color: "#2e3f5c", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              UTC
            </span>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: "0.72rem",
                color: "#3b82f6",
                letterSpacing: "0.05em",
              }}
            >
              {time}
            </span>
          </div>
        </div>
      )}

      {/* Collapsed status dot */}
      {collapsed && (
        <div
          style={{
            padding: "14px 0",
            display: "flex",
            justifyContent: "center",
            borderTop: "1px solid #1e2a3d",
          }}
        >
          <div
            className="animate-pulse-dot"
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "#10b981",
              boxShadow: "0 0 8px #10b981",
            }}
          />
        </div>
      )}
    </aside>
  );
}
