"use client";

import MainLayout from "@/components/layout/MainLayout";
import { notifyApiError } from "@/components/ui/ApiStatusBanner";
import { api, type AlertRecord } from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

const typeColors: Record<string, string> = {
  SETUP: "var(--accent-blue)",
  RISK: "var(--accent-yellow)",
  SCANNER: "var(--accent-cyan)",
};

const channelIcons: Record<string, string> = {
  WEB: "🌐",
  TELEGRAM: "📱",
  EMAIL: "📧",
};

function inferAlertType(message: string): string {
  const m = message.toUpperCase();
  if (m.includes("RISK") || m.includes("DAILY")) return "RISK";
  if (m.includes("SCANNER")) return "SCANNER";
  return "SETUP";
}

function formatTime(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [alertEnabled, setAlertEnabled] = useState(true);
  const [telegramId, setTelegramId] = useState("");
  const [email, setEmail] = useState("");
  const [feedback, setFeedback] = useState<{ text: string; ok: boolean } | null>(null);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getAlerts();
      setAlerts(Array.isArray(res.alerts) ? res.alerts : []);
    } catch (e) {
      notifyApiError(e instanceof Error ? e.message : "Gagal memuat alerts");
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAlerts();
    const id = setInterval(loadAlerts, 60000);
    return () => clearInterval(id);
  }, [loadAlerts]);

  useEffect(() => {
    api.getRiskSettings().then((res) => {
      const s = res.settings;
      if (s.telegram_chat_id) setTelegramId(String(s.telegram_chat_id));
      if (s.email) setEmail(s.email);
      if (s.alert_enabled != null) setAlertEnabled(s.alert_enabled);
    }).catch(() => {});
  }, []);

  const runTestAlert = async () => {
    setTesting(true);
    setFeedback(null);
    try {
      const res = await api.testAlert();
      const ok = res.results?.some((r) => r.success);
      setFeedback({
        text: ok ? "Test alert terkirim (cek Telegram/Web)" : "Test alert gagal — periksa konfigurasi",
        ok: !!ok,
      });
      await loadAlerts();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Test alert gagal";
      notifyApiError(msg);
      setFeedback({ text: msg, ok: false });
    } finally {
      setTesting(false);
    }
  };

  const saveSettings = async () => {
    try {
      await api.updateAlertSettings({
        telegram_chat_id: telegramId || undefined,
        email: email || undefined,
        alert_enabled: alertEnabled,
      });
      setFeedback({ text: "Pengaturan alert disimpan", ok: true });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Gagal menyimpan pengaturan";
      notifyApiError(msg);
      setFeedback({ text: msg, ok: false });
    }
  };

  return (
    <MainLayout>
      <AlertsPageHeader testing={testing} onTest={runTestAlert} />

      {feedback && (
        <div
          style={{
            marginBottom: 16,
            padding: "10px 14px",
            borderRadius: 8,
            fontSize: "0.8rem",
            fontWeight: 600,
            background: feedback.ok ? "rgba(16,185,129,0.12)" : "rgba(239,68,68,0.12)",
            color: feedback.ok ? "#6ee7b7" : "#fca5a5",
          }}
        >
          {feedback.text}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 24 }}>
        <AlertList loading={loading} alerts={alerts} />
        <AlertSettingsPanel
          alertEnabled={alertEnabled}
          setAlertEnabled={setAlertEnabled}
          telegramId={telegramId}
          setTelegramId={setTelegramId}
          email={email}
          setEmail={setEmail}
          onSave={saveSettings}
        />
      </div>
    </MainLayout>
  );
}

function AlertsPageHeader({ testing, onTest }: { testing: boolean; onTest: () => void }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
      <div>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Alerts</h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "4px 0 0" }}>
          Notification center for trade setups and risk events
        </p>
      </div>
      <button className="btn-primary" onClick={onTest} disabled={testing}>
        {testing ? "Mengirim…" : "🔔 Test Alert"}
      </button>
    </div>
  );
}

function AlertList({ loading, alerts }: { loading: boolean; alerts: AlertRecord[] }) {
  if (loading) {
    return (
      <div className="glass-card" style={{ padding: 48, textAlign: "center", color: "var(--text-muted)" }}>
        Memuat riwayat alert…
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="glass-card" style={{ padding: 48, textAlign: "center", color: "var(--text-muted)" }}>
        Belum ada alert. Jalankan scanner atau klik Test Alert.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {alerts.map((a) => (
        <AlertCard key={a.id} alert={a} />
      ))}
    </div>
  );
}

function AlertCard({ alert: a }: { alert: AlertRecord }) {
  const type = inferAlertType(a.message);
  const title = a.message.split("\n")[0].slice(0, 80);

  return (
    <div className="glass-card" style={{ padding: "16px 20px" }}>
      <AlertCardHeader alert={a} type={type} title={title} />
      <div
        style={{
          background: "rgba(255,255,255,0.02)",
          borderRadius: 8,
          padding: "10px 14px",
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: "0.78rem",
          color: "var(--text-secondary)",
          lineHeight: 1.6,
          whiteSpace: "pre-line",
        }}
      >
        {a.message}
      </div>
    </div>
  );
}

function AlertCardHeader({ alert: a, type, title }: { alert: AlertRecord; type: string; title: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
      <AlertTitleRow type={type} title={title} />
      <AlertMeta alert={a} />
    </div>
  );
}

function AlertTitleRow({ type, title }: { type: string; title: string }) {
  return (
    <FlexRow>
      <StatusDot color={typeColors[type] || "var(--text-muted)"} />
      <span style={{ fontWeight: 700, fontSize: "0.9rem" }}>{title}</span>
    </FlexRow>
  );
}

function StatusDot({ color }: { color: string }) {
  return <FlexRow style={{ width: 8, height: 8, borderRadius: "50%", background: color }} />;
}

function AlertMeta({ alert: a }: { alert: AlertRecord }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{ fontSize: "0.75rem" }}>
        {channelIcons[a.channel] || "📢"} {a.channel}
      </span>
      <span
        style={{
          fontSize: "0.65rem",
          fontWeight: 700,
          color:
            a.status === "SENT"
              ? "var(--accent-green)"
              : a.status === "FAILED"
                ? "var(--accent-red)"
                : "var(--text-muted)",
        }}
      >
        {a.status}
      </span>
      <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
        {formatTime(a.sent_at)}
      </span>
    </div>
  );
}

function AlertSettingsPanel({
  alertEnabled,
  setAlertEnabled,
  telegramId,
  setTelegramId,
  email,
  setEmail,
  onSave,
}: {
  alertEnabled: boolean;
  setAlertEnabled: (v: boolean) => void;
  telegramId: string;
  setTelegramId: (v: string) => void;
  email: string;
  setEmail: (v: string) => void;
  onSave: () => void;
}) {
  return (
    <div className="glass-card" style={{ padding: 24, height: "fit-content" }}>
      <h3 style={{ fontSize: "0.9rem", fontWeight: 700, margin: "0 0 20px 0" }}>Alert Channels</h3>

      <label style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16, cursor: "pointer" }}>
        <input type="checkbox" checked={alertEnabled} onChange={(e) => setAlertEnabled(e.target.checked)} />
        <span style={{ fontSize: "0.85rem" }}>Alerts enabled</span>
      </label>

      <div style={{ marginBottom: 14 }}>
        <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600, display: "block", marginBottom: 6 }}>
          Telegram Chat ID
        </label>
        <input className="input-field" value={telegramId} onChange={(e) => setTelegramId(e.target.value)} placeholder="Opsional" />
      </div>

      <div style={{ marginBottom: 14 }}>
        <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600, display: "block", marginBottom: 6 }}>
          Email
        </label>
        <input className="input-field" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Opsional" />
      </div>

      <button className="btn-primary" style={{ width: "100%" }} onClick={onSave}>
        Simpan Pengaturan
      </button>

      <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: 16, lineHeight: 1.5 }}>
        Web alerts via WebSocket. Telegram butuh <code>TELEGRAM_BOT_TOKEN</code> di backend. Email butuh SMTP di <code>.env</code>.
      </p>
    </div>
  );
}

function FlexRow({ children, style }: { children?: React.ReactNode; style?: React.CSSProperties }) {
  if (style && !children) {
    return <div style={style} />;
  }
  return <div style={{ display: "flex", alignItems: "center", gap: 10, ...style }}>{children}</div>;
}
