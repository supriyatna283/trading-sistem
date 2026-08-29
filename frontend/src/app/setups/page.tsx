"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatPrice, timeAgo } from "@/lib/utils";
import { Gauge, BBPanelDetail, ScoreRing } from "@/components/setups/SetupComponents";
import ConfirmModal from "@/components/ui/ConfirmModal";
import toast from "react-hot-toast";
import SetupCard from "@/components/setups/SetupCard";

// ── Components ───────────────────────────────────────────────────────────────
function TimeAgo({ date }: { date: string }) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setTick(t => t + 1), 60000);
    return () => clearInterval(timer);
  }, []);
  return <span>{timeAgo(date)}</span>;
}

// ── Types ────────────────────────────────────────────────────────────────────
type StatusFilter = "ALL" | "ACTIVE" | "TRIGGERED" | "EXPIRED";
type SortKey = "newest" | "oldest" | "score_desc" | "score_asc" | "rr_desc";
type ConfirmAction = { type: "delete_one"; id: number; symbol: string } | { type: "delete_all" } | null;

const SCORE_PRESETS = [
  { label: "ALL", value: 0, color: "#94a3b8" },
  { label: "50+", value: 50, color: "#60a5fa" },
  { label: "65+", value: 65, color: "#10b981" },
  { label: "80+", value: 80, color: "#f59e0b" },
];

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "newest", label: "↓ Newest" },
  { key: "oldest", label: "↑ Oldest" },
  { key: "score_desc", label: "↓ Score" },
  { key: "score_asc", label: "↑ Score" },
  { key: "rr_desc", label: "↓ R:R" },
];

const PAGE_SIZE = 20;

export default function SetupsPage() {
  const router = useRouter();
  const [setups, setSetups] = useState<any[]>([]);
  const [allSymbols, setAllSymbols] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generatingSymbol, setGeneratingSymbol] = useState("");
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null);

  // Filters
  const [filter, setFilter] = useState<StatusFilter>("ALL");
  const [minScore, setMinScore] = useState(0);
  const [sortKey, setSortKey] = useState<SortKey>("newest");
  const [dirFilter, setDirFilter] = useState<"ALL" | "BUY" | "SELL">("ALL");

  // UI state
  const [executingId, setExecutingId] = useState<number | null>(null);
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);
  const [page, setPage] = useState(1);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  // ── Init & polling ──────────────────────────────────────────────────────────
  useEffect(() => {
    const init = async () => {
      await Promise.all([fetchSetups(), fetchSchedulerStatus(), fetchSymbols()]);
    };
    init();
    const timer = setInterval(() => { fetchSetups(); fetchSchedulerStatus(); }, 60000);
    return () => clearInterval(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchSymbols = async () => {
    try {
      const res = await api.getSymbols();
      setAllSymbols(Array.isArray(res?.symbols) ? res.symbols : []);
    } catch (_) {}
  };

  const fetchSetups = async () => {
    setIsLoading(true);
    try {
      const res = await api.getSetups();
      setSetups(Array.isArray(res?.setups) ? res.setups : []);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchSchedulerStatus = async () => {
    try {
      const res = await api.getSchedulerStatus();
      setSchedulerStatus(res?.scheduler || null);
    } catch (_) {}
  };

  // ── Actions ─────────────────────────────────────────────────────────────────
  const forceSchedulerRun = async () => {
    setGenerating(true); setGeneratingSymbol("auto-scanner...");
    try { await api.triggerScheduler(); await fetchSetups(); await fetchSchedulerStatus(); }
    catch (err) { console.error(err); } finally { setGenerating(false); setGeneratingSymbol(""); }
  };

  const generateAllSignals = async () => {
    setGenerating(true);
    try { setGeneratingSymbol("scanning markets..."); await api.generateAllSetups("1h"); await fetchSetups(); }
    catch (err) { console.error(err); } finally { setGenerating(false); setGeneratingSymbol(""); }
  };

  const handleExecute = useCallback(async (id: number) => {
    setExecutingId(id);
    try {
      await api.executeFromSetup(id);
      toast.success("Setup executed successfully");
      await fetchSetups();
    } catch (e: any) {
      toast.error(e.message || "Failed to execute setup");
    } finally {
      setExecutingId(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleConfirmAction = async () => {
    if (!confirmAction) return;
    try {
      if (confirmAction.type === "delete_one") {
        await api.deleteSetup(confirmAction.id);
        toast.success("Setup deleted");
      } else if (confirmAction.type === "delete_all") {
        await api.clearAllSetups();
        toast.success("All setups deleted");
      }
      await fetchSetups();
    } catch (e: any) {
      toast.error(e.message || "Failed to delete setup(s)");
    } finally {
      setConfirmAction(null);
    }
  };

  const toggleExpand = (id: number) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  // ── Filtering + Sorting ──────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    let arr = filter === "ALL" ? setups : setups.filter(s => s.status === filter);
    if (dirFilter !== "ALL") arr = arr.filter(s => s.direction === dirFilter);
    if (minScore > 0) arr = arr.filter(s => (s.signal_score ?? s.confluence_score ?? 0) >= minScore);

    switch (sortKey) {
      case "oldest":     arr = [...arr].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()); break;
      case "score_desc": arr = [...arr].sort((a, b) => (b.signal_score ?? b.confluence_score ?? 0) - (a.signal_score ?? a.confluence_score ?? 0)); break;
      case "score_asc":  arr = [...arr].sort((a, b) => (a.signal_score ?? a.confluence_score ?? 0) - (b.signal_score ?? b.confluence_score ?? 0)); break;
      case "rr_desc":    arr = [...arr].sort((a, b) => (b.risk_reward ?? 0) - (a.risk_reward ?? 0)); break;
      default: /* newest */ arr = [...arr].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    }
    return arr;
  }, [setups, filter, dirFilter, minScore, sortKey]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = useMemo(() => filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE), [filtered, page]);

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1); }, [filter, minScore, dirFilter, sortKey]);

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <MainLayout>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse-dot { 0%,100%{opacity:1;} 50%{opacity:0.4;} }
        .setup-card:hover { transform: translateY(-2px); box-shadow: 0 16px 40px rgba(0,0,0,0.3); }
        .setup-card { transition: transform 0.2s, box-shadow 0.2s; }
      `}</style>

      {/* ── Confirm Modal ── */}
      <ConfirmModal
        isOpen={!!confirmAction}
        title={confirmAction?.type === "delete_all" ? "Delete ALL Setups?" : `Delete ${(confirmAction as any)?.symbol ?? "setup"}?`}
        message={
          confirmAction?.type === "delete_all"
            ? "This will permanently remove all setups from the database. Journal entries will be unlinked."
            : "This will permanently delete this setup. This action cannot be undone."
        }
        confirmLabel="Delete"
        danger
        onConfirm={handleConfirmAction}
        onCancel={() => setConfirmAction(null)}
      />

      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row md:justify-between md:items-start mb-7 gap-4 md:gap-0">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
            <span style={{ fontSize: "0.7rem", fontWeight: 800, letterSpacing: "0.14em", color: "#f59e0b", textTransform: "uppercase" }}>⚡ INTRADAY ENGINE</span>
          </div>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 900, letterSpacing: "-0.04em", margin: 0, background: "linear-gradient(135deg, #fff 40%, #94a3b8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Signal Dashboard
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", margin: "6px 0 0" }}>
            FIB · MACD · RSI · Multi-TF Confluence — {allSymbols.length} pairs monitored
          </p>
        </div>
        <div className="flex gap-2 flex-wrap w-full md:w-auto">
          <button
            className="btn-primary"
            onClick={generateAllSignals}
            disabled={generating}
            style={{ opacity: generating ? 0.7 : 1, display: "flex", alignItems: "center", gap: 8, padding: "10px 18px", fontWeight: 700, fontSize: "0.82rem" }}
          >
            {generating
              ? <><span style={{ width: 13, height: 13, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.8s linear infinite", display: "inline-block" }} />Scanning {generatingSymbol}</>
              : "⚡ Scan Markets"}
          </button>
          <button
            onClick={forceSchedulerRun}
            disabled={generating}
            style={{ padding: "10px 16px", borderRadius: 10, border: "1px solid rgba(139,92,246,0.3)", background: "rgba(139,92,246,0.08)", color: "#a78bfa", cursor: "pointer", fontWeight: 700, fontSize: "0.78rem", opacity: generating ? 0.5 : 1 }}
          >
            🤖 Auto
          </button>
          <button
            onClick={() => setConfirmAction({ type: "delete_all" })}
            style={{ padding: "10px 16px", borderRadius: 10, border: "1px solid rgba(239,68,68,0.25)", background: "rgba(239,68,68,0.05)", color: "#f87171", cursor: "pointer", fontWeight: 700, fontSize: "0.78rem" }}
          >
            🗑
          </button>
        </div>
      </div>

      {/* ── Scheduler Banner ── */}
      {schedulerStatus && (
        <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap", padding: "12px 18px", marginBottom: 20, borderRadius: 12, background: "rgba(16,185,129,0.04)", border: "1px solid rgba(16,185,129,0.12)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#10b981", boxShadow: "0 0 8px #10b981", animation: "pulse-dot 2s infinite" }} />
            <span style={{ fontWeight: 800, fontSize: "0.78rem", color: "#10b981", letterSpacing: "0.05em" }}>ENGINE LIVE</span>
          </div>
          {schedulerStatus.last_run && <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Last: <strong style={{ color: "#fff" }}>{new Date(schedulerStatus.last_run).toLocaleTimeString()}</strong></span>}
          {schedulerStatus.next_run && <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Next: <strong style={{ color: "#60a5fa" }}>{new Date(schedulerStatus.next_run).toLocaleTimeString()}</strong></span>}
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Generated: <strong style={{ color: "#10b981" }}>{schedulerStatus.last_generated ?? 0}</strong></span>
        </div>
      )}

      {/* ── Institutional SOP Banner ── */}
      <div style={{ background: "rgba(245,158,11,0.05)", border: "1px solid rgba(245,158,11,0.2)", borderRadius: 12, padding: "16px 20px", marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <span style={{ fontSize: "1.2rem" }}>📜</span>
          <span style={{ fontSize: "0.85rem", fontWeight: 800, color: "#f59e0b", letterSpacing: "0.05em", textTransform: "uppercase" }}>Golden Rules (Trading SOP)</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 16 }}>
          <div>
            <div style={{ fontSize: "0.75rem", fontWeight: 800, color: "#fff", marginBottom: 4 }}>1. Gunakan Scanner Dulu</div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", lineHeight: 1.5 }}>Jangan sembarang buka chart. Gunakan menu <strong>Scanner</strong> untuk mencari koin bervolume tinggi / trending. RSI & MACD sering memberi sinyal palsu di pasar sideways.</div>
          </div>
          <div>
            <div style={{ fontSize: "0.75rem", fontWeight: 800, color: "#fff", marginBottom: 4 }}>2. Jangan Berdebat dengan Stop Loss</div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", lineHeight: 1.5 }}>Pasang <strong>Stop Loss</strong> di Exchange sesuai anjuran AI (di luar level Fib 0/100%) dan lupakan. Jangan menggeser SL karena berharap harga berbalik.</div>
          </div>
          <div>
            <div style={{ fontSize: "0.75rem", fontWeight: 800, color: "#fff", marginBottom: 4 }}>3. Eksekusi Ala Penembak Runduk</div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", lineHeight: 1.5 }}>Tunggu sampai harga masuk area Fibonacci, RSI Oversold/Overbought, dan tunggu <strong>Crossover MACD</strong> sebelum klik BUY/SELL. Kesabaran adalah kunci.</div>
          </div>
        </div>
      </div>
      {/* ── Score Filter ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
        <span style={{ fontSize: "0.72rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em", whiteSpace: "nowrap" }}>🎯 Score</span>
        {SCORE_PRESETS.map(p => {
          const isActive = minScore === p.value;
          const count = p.value === 0 ? setups.length : setups.filter(s => (s.signal_score ?? s.confluence_score ?? 0) >= p.value).length;
          return (
            <button key={p.label} onClick={() => setMinScore(p.value)} style={{ padding: "5px 14px", borderRadius: 8, border: isActive ? `1px solid ${p.color}60` : "1px solid var(--border)", background: isActive ? `${p.color}18` : "transparent", color: isActive ? p.color : "var(--text-muted)", fontWeight: 800, fontSize: "0.78rem", cursor: "pointer", transition: "all 0.15s", display: "flex", alignItems: "center", gap: 5 }}>
              {p.label}<span style={{ opacity: 0.65, fontSize: "0.7rem", fontWeight: 600 }}>{count}</span>
            </button>
          );
        })}

        {/* Direction filter */}
        <div style={{ width: 1, height: 16, background: "var(--border)" }} />
        {(["ALL", "BUY", "SELL"] as const).map(d => (
          <button key={d} onClick={() => setDirFilter(d)} style={{ padding: "5px 12px", borderRadius: 8, border: dirFilter === d ? `1px solid ${d === "BUY" ? "#22c55e60" : d === "SELL" ? "#ef444460" : "rgba(255,255,255,0.2)"}` : "1px solid var(--border)", background: dirFilter === d ? (d === "BUY" ? "rgba(34,197,94,0.12)" : d === "SELL" ? "rgba(239,68,68,0.12)" : "rgba(255,255,255,0.06)") : "transparent", color: dirFilter === d ? (d === "BUY" ? "#22c55e" : d === "SELL" ? "#ef4444" : "#fff") : "var(--text-muted)", fontWeight: 800, fontSize: "0.75rem", cursor: "pointer", transition: "all 0.15s" }}>
            {d === "BUY" ? "▲ LONG" : d === "SELL" ? "▼ SHORT" : "ALL DIR"}
          </button>
        ))}
      </div>

      {/* ── Status Tabs + Sort ── */}
      <div className="flex gap-2 mb-5 flex-wrap items-center">
        {(["ALL", "ACTIVE", "TRIGGERED", "EXPIRED"] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{ background: filter === f ? "rgba(59,130,246,0.12)" : "transparent", border: filter === f ? "1px solid rgba(59,130,246,0.35)" : "1px solid var(--border)", color: filter === f ? "#60a5fa" : "var(--text-muted)", padding: "6px 16px", borderRadius: 8, fontSize: "0.8rem", fontWeight: 700, cursor: "pointer" }}>
            {f}{f !== "ALL" && <span style={{ opacity: 0.5, marginLeft: 5 }}>{setups.filter(s => s.status === f).length}</span>}
          </button>
        ))}

        {/* Sort */}
        <div className="ml-0 mt-2 sm:mt-0 sm:ml-auto flex items-center gap-2 w-full sm:w-auto justify-between sm:justify-start">
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 700 }}>SORT</span>
          <select
            value={sortKey}
            onChange={e => setSortKey(e.target.value as SortKey)}
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid var(--border)", borderRadius: 8, padding: "5px 10px", color: "var(--text-primary)", fontSize: "0.78rem", cursor: "pointer", outline: "none" }}
          >
            {SORT_OPTIONS.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
          </select>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{filtered.length} signals</span>
        </div>
      </div>

      {/* ── Loading ── */}
      {isLoading && (
        <div style={{ padding: 60, textAlign: "center", color: "var(--text-muted)" }}>
          <div style={{ width: 28, height: 28, border: "3px solid var(--border)", borderTopColor: "#3b82f6", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 14px" }} />
          Synchronizing…
        </div>
      )}

      {/* ── Empty ── */}
      {!isLoading && filtered.length === 0 && (
        <div className="glass-card" style={{ padding: 70, textAlign: "center", border: "1px dashed var(--border)" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: 16 }}>📡</div>
          <h3 style={{ fontWeight: 800, marginBottom: 8 }}>No Signals Detected</h3>
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: 20, maxWidth: 400, margin: "0 auto 20px" }}>
            Engine is monitoring {allSymbols.length} pairs. No high-probability intraday setups found.
          </p>
          <button className="btn-primary" onClick={generateAllSignals} disabled={generating} style={{ padding: "11px 22px", fontWeight: 700 }}>
            ⚡ Force Deep Scan
          </button>
        </div>
      )}

      {/* ── Cards Grid ── */}
      {!isLoading && filtered.length > 0 && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(420px, 100%), 1fr))", gap: 20 }}>
            {paged.map((s: any, i: number) => (
              <SetupCard 
                key={s.id || i}
                s={s}
                i={i}
                expandedIds={expandedIds}
                toggleExpand={toggleExpand}
                executingId={executingId}
                handleExecute={handleExecute}
                setConfirmAction={setConfirmAction}
                fetchSetups={fetchSetups}
                router={router}
              />
            ))}
          </div>

          {/* ── Pagination ── */}
          {totalPages > 1 && (
            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 8, marginTop: 32 }}>
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid var(--border)", background: "rgba(255,255,255,0.04)", color: page === 1 ? "var(--text-muted)" : "var(--text-primary)", cursor: page === 1 ? "not-allowed" : "pointer", fontSize: "0.82rem", fontWeight: 700, opacity: page === 1 ? 0.4 : 1 }}
              >
                ← Prev
              </button>
              {Array.from({ length: totalPages }, (_, idx) => idx + 1)
                .filter(p => p === 1 || p === totalPages || Math.abs(p - page) <= 2)
                .reduce<(number | "…")[]>((acc, p, i, arr) => {
                  if (i > 0 && (p as number) - (arr[i - 1] as number) > 1) acc.push("…");
                  acc.push(p);
                  return acc;
                }, [])
                .map((p, idx) =>
                  p === "…" ? (
                    <span key={`sep-${idx}`} style={{ color: "var(--text-muted)", padding: "0 4px" }}>…</span>
                  ) : (
                    <button
                      key={p}
                      onClick={() => setPage(p as number)}
                      style={{ padding: "7px 13px", borderRadius: 8, border: page === p ? "1px solid rgba(59,130,246,0.4)" : "1px solid var(--border)", background: page === p ? "rgba(59,130,246,0.15)" : "rgba(255,255,255,0.04)", color: page === p ? "#60a5fa" : "var(--text-secondary)", cursor: "pointer", fontSize: "0.82rem", fontWeight: 700 }}
                    >
                      {p}
                    </button>
                  )
                )}
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid var(--border)", background: "rgba(255,255,255,0.04)", color: page === totalPages ? "var(--text-muted)" : "var(--text-primary)", cursor: page === totalPages ? "not-allowed" : "pointer", fontSize: "0.82rem", fontWeight: 700, opacity: page === totalPages ? 0.4 : 1 }}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </MainLayout>
  );
}
