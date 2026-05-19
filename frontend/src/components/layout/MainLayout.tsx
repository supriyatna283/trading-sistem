"use client";

import Sidebar from "./Sidebar";
import ApiStatusBanner from "@/components/ui/ApiStatusBanner";
import { useState, useEffect } from "react";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  // Sidebar starts at 228px, collapses to 68px
  // We watch sidebar width via a custom event or just use fixed breakpoints
  const [sideW, setSideW] = useState(228);

  useEffect(() => {
    const handler = (e: CustomEvent) => setSideW(e.detail as number);
    window.addEventListener("sidebar-width" as any, handler);
    return () => window.removeEventListener("sidebar-width" as any, handler);
  }, []);

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg)" }}>
      <Sidebar onWidthChange={setSideW} />
      <main
        style={{
          flex: 1,
          marginLeft: sideW,
          padding: "28px 32px 40px",
          minHeight: "100vh",
          transition: "margin-left 0.22s cubic-bezier(.4,0,.2,1)",
          maxWidth: `calc(100vw - ${sideW}px)`,
        }}
      >
        <ApiStatusBanner />
        {children}
      </main>
    </div>
  );
}
