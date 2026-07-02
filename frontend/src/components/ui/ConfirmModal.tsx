"use client";

import { useEffect } from "react";

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmModal({
  isOpen,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  // Close on ESC
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  const confirmColor = danger ? "#ef4444" : "#3b82f6";
  const confirmBg = danger ? "rgba(239,68,68,0.15)" : "rgba(59,130,246,0.15)";
  const confirmBorder = danger ? "rgba(239,68,68,0.4)" : "rgba(59,130,246,0.4)";

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onCancel}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.6)",
          backdropFilter: "blur(4px)",
          zIndex: 9998,
          animation: "fadeIn 0.15s ease",
        }}
      />
      {/* Modal */}
      <div
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          zIndex: 9999,
          width: "min(420px, 90vw)",
          background: "rgba(13,17,28,0.98)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: 16,
          padding: "28px 28px 22px",
          boxShadow: "0 24px 80px rgba(0,0,0,0.6)",
          animation: "slideUp 0.2s ease",
        }}
      >
        {/* Icon */}
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: "50%",
            background: danger ? "rgba(239,68,68,0.1)" : "rgba(59,130,246,0.1)",
            border: `1px solid ${confirmBorder}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "1.4rem",
            marginBottom: 18,
          }}
        >
          {danger ? "⚠️" : "❓"}
        </div>

        {/* Title */}
        <h3
          style={{
            fontSize: "1rem",
            fontWeight: 800,
            margin: "0 0 10px",
            color: "var(--text-primary)",
            letterSpacing: "-0.02em",
          }}
        >
          {title}
        </h3>

        {/* Message */}
        <p
          style={{
            fontSize: "0.85rem",
            color: "var(--text-secondary)",
            lineHeight: 1.6,
            margin: "0 0 24px",
          }}
        >
          {message}
        </p>

        {/* Actions */}
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={onCancel}
            style={{
              flex: 1,
              padding: "10px 0",
              borderRadius: 10,
              border: "1px solid var(--border)",
              background: "rgba(255,255,255,0.04)",
              color: "var(--text-secondary)",
              fontSize: "0.85rem",
              fontWeight: 700,
              cursor: "pointer",
              transition: "all 0.15s",
            }}
            onMouseEnter={e => ((e.target as HTMLButtonElement).style.background = "rgba(255,255,255,0.08)")}
            onMouseLeave={e => ((e.target as HTMLButtonElement).style.background = "rgba(255,255,255,0.04)")}
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            style={{
              flex: 1,
              padding: "10px 0",
              borderRadius: 10,
              border: `1px solid ${confirmBorder}`,
              background: confirmBg,
              color: confirmColor,
              fontSize: "0.85rem",
              fontWeight: 800,
              cursor: "pointer",
              transition: "all 0.15s",
            }}
            onMouseEnter={e =>
              ((e.target as HTMLButtonElement).style.background = danger
                ? "rgba(239,68,68,0.25)"
                : "rgba(59,130,246,0.25)")
            }
            onMouseLeave={e => ((e.target as HTMLButtonElement).style.background = confirmBg)}
          >
            {confirmLabel}
          </button>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideUp { from { opacity: 0; transform: translate(-50%, -45%); } to { opacity: 1; transform: translate(-50%, -50%); } }
      `}</style>
    </>
  );
}
