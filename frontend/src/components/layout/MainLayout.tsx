"use client";

import Sidebar from "./Sidebar";
import ApiStatusBanner from "@/components/ui/ApiStatusBanner";
import { useState, useEffect } from "react";
import { Menu } from "lucide-react";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  // Sidebar starts at 228px, collapses to 68px
  const [sideW, setSideW] = useState(228);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handler = (e: CustomEvent) => setSideW(e.detail as number);
    window.addEventListener("sidebar-width" as any, handler);
    return () => window.removeEventListener("sidebar-width" as any, handler);
  }, []);

  return (
    <div className="flex min-h-screen bg-[var(--bg)]">
      <Sidebar 
        onWidthChange={setSideW} 
        mobileOpen={mobileOpen} 
        onCloseMobile={() => setMobileOpen(false)} 
      />
      <main
        className="flex-1 w-full transition-all duration-300 ease-in-out md:max-w-none"
        style={{
          // On mobile, margin is 0. On md+ screens, it's sideW.
          // Using a CSS variable to pass the dynamic width to Tailwind/CSS
          marginLeft: "var(--main-ml, 0px)",
        }}
        // Inject the dynamic margin for desktop via inline styles while letting Tailwind handle mobile (ml-0).
        // A cleaner way is using styled components or styled jsx, but here we can just use inline styles with media query if possible.
        // Actually, since we can't easily do media query in inline style, we'll just set the padding and margin conditionally based on window size? No, SSR.
      >
        <style dangerouslySetInnerHTML={{__html: `
          @media (min-width: 768px) {
            .responsive-main {
              margin-left: ${sideW}px !important;
              max-width: calc(100vw - ${sideW}px) !important;
              padding: 28px 32px 40px !important;
            }
          }
          @media (max-width: 767px) {
            .responsive-main {
              margin-left: 0 !important;
              max-width: 100vw !important;
              padding: 16px 16px 80px !important;
            }
          }
        `}} />
        <div className="responsive-main" style={{ minHeight: "100vh", transition: "all 0.22s cubic-bezier(.4,0,.2,1)" }}>
          {/* Mobile Header (Hamburger) */}
          <div className="md:hidden flex items-center justify-between mb-6 pb-4 border-b border-white/5">
            <div className="flex items-center gap-3">
              <button 
                onClick={() => setMobileOpen(true)}
                className="p-2 -ml-2 rounded-lg bg-white/5 border border-white/10 text-white"
              >
                <Menu size={20} />
              </button>
              <div className="font-outfit font-black text-lg bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
                TradingSistem
              </div>
            </div>
          </div>
          
          <ApiStatusBanner />
          {children}
        </div>
      </main>
    </div>
  );
}
