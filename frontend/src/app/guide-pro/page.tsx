"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState } from "react";

/* ── Types ── */
type ToolId = "killzone" | "pd-zones" | "sweep" | "ob-strength" | "fvg-breaker" | "position";

interface Tool {
  id: ToolId;
  icon: string;
  name: string;
  tagline: string;
  color: string;
  what: string;
  why: string;
  how: string[];
  steps: { step: string; detail: string }[];
  rules: string[];
  example: string;
  dontDo: string[];
}

const TOOLS: Tool[] = [
  {
    id: "killzone",
    icon: "🎯",
    name: "Killzone Timer",
    tagline: "Kapan waktu terbaik untuk trading?",
    color: "#10b981",
    what: "Killzone adalah jendela waktu tertentu dalam sehari di mana Smart Money (bank & institusi) paling aktif bergerak. Di luar waktu ini, market cenderung choppy & unpredictable.",
    why: "90% trader retail rugi karena masuk market di waktu yang salah. Seperti memancing di sungai yang salah — tidak peduli seberapa bagus kailmu, ikannya tidak ada di sana.",
    how: [
      "Buka tab Killzone Timer",
      "Lihat session mana yang sedang aktif (warna hijau = aktif sekarang)",
      "Tunggu hingga salah satu killzone mulai sebelum setup trading",
    ],
    steps: [
      { step: "ASIA (00:00–07:00 UTC)", detail: "JANGAN TRADE. Hanya observasi. Catat harga tertinggi (Asia High) dan terendah (Asia Low) — ini akan jadi target sweep nanti." },
      { step: "LONDON OPEN (07:00–10:00 UTC)", detail: "Killzone pertama. Market sering sweep Asia High ATAU Low secara palsu (Judas Swing) sebelum berbalik ke arah sebenarnya." },
      { step: "NEW YORK OPEN (12:00–15:00 UTC)", detail: "Killzone paling kuat. Konfirmasi atau pembalikan dari arah London. Setup terbaik untuk entry." },
      { step: "NY LUNCH & CLOSE (16:00+)", detail: "Volume turun drastis. Hindari entry baru. Close position jika tidak nyaman hold overnight." },
    ],
    rules: [
      "✅ Entry HANYA di dalam Killzone",
      "✅ Jika tidak ada killzone aktif = tidak ada trade",
      "❌ Jangan trade saat ASIA — itu jebakan",
      "❌ Jangan trade saat weekend — spread melebar, manipulasi tinggi",
    ],
    example: "Kamu lihat harga Bitcoin sweep Asia Low di jam 07:15 UTC (London Open). Ini sinyal: Smart Money ambil likuiditas di bawah, kemungkinan besar akan naik. TUNGGU konfirmasi, baru entry BUY.",
    dontDo: ["Trading jam 2 pagi karena 'bosan'", "Masuk market saat DEAD ZONE", "Ignore session overlap"],
  },
  {
    id: "pd-zones",
    icon: "📊",
    name: "Premium / Discount Zones",
    tagline: "Beli murah, jual mahal — seperti yang institusi lakukan",
    color: "#3b82f6",
    what: "PD Zone adalah konsep bahwa market selalu bergerak dari zona PREMIUM (mahal) ke DISCOUNT (murah) dan sebaliknya. Institusi SELALU beli di Discount dan jual di Premium — tidak pernah sebaliknya.",
    why: "Retail trader sering beli di puncak dan jual di bawah — kebalikan dari institusi. Dengan mengetahui apakah price sekarang di Premium atau Discount, kamu bisa masuk searah dengan Smart Money.",
    how: [
      "Buka tab P/D Zones",
      "Masukkan simbol (contoh: BTCUSDT) dan timeframe HTF (1d atau 4h)",
      "Klik Analyze untuk melihat posisi price sekarang",
    ],
    steps: [
      { step: "Tentukan Swing High dan Low", detail: "Ambil harga tertinggi dan terendah dari beberapa candle terakhir pada HTF (1d/4h). Ini adalah range reference kamu." },
      { step: "Cek posisi price saat ini", detail: "Sistem menghitung Fibonacci 50% (Equilibrium). Di atas 62% = Premium. Di bawah 38% = Discount." },
      { step: "Tentukan bias", detail: "Price di Discount Zone → Cari setup BUY saja. Price di Premium Zone → Cari setup SELL saja. Di Equilibrium → Tunggu." },
      { step: "Konfirmasi dengan OTE", detail: "OTE (Optimal Trade Entry) = Fibonacci 62–79%. Ini zona terbaik untuk entry. Premium OTE = jual, Discount OTE = beli." },
    ],
    rules: [
      "✅ BUY hanya saat price di Discount (<38% range)",
      "✅ SELL hanya saat price di Premium (>62% range)",
      "✅ Gunakan HTF (4h atau 1d) sebagai referensi utama",
      "❌ Jangan BUY di Premium — kamu beli dari institusi yang sedang jual",
      "❌ Jangan SELL di Discount — kamu jual ke institusi yang sedang beli",
    ],
    example: "BTC range hari ini: Low $60,000, High $66,000. Range = $6,000. Equilibrium = $63,000. Harga sekarang = $61,200 → ini di Discount Zone (35%). Bias = ONLY BUY. Tunggu FVG atau OB di bawah harga sekarang, lalu entry BUY.",
    dontDo: ["BUY saat price di atas 62% range", "Gunakan LTF untuk PD Zone reference", "Ignore HTF bias"],
  },
  {
    id: "sweep",
    icon: "🌊",
    name: "Liquidity Sweep Detector",
    tagline: "Deteksi kapan Smart Money 'berburu' stop loss kamu",
    color: "#ef4444",
    what: "Liquidity Sweep adalah saat Smart Money sengaja mendorong harga melewati level penting (high/low, equal highs/lows) untuk trigger stop loss retail trader — mengambil 'likuiditas' — sebelum berbalik ke arah sebenarnya.",
    why: "Stop loss kamu adalah ORDER BUY/SELL bagi institusi. Mereka BUTUH volume besar untuk mengisi posisi mereka. Dengan mendeteksi sweep, kamu bisa masuk SETELAH institusi selesai 'berburu' dan ikut arah sebenarnya.",
    how: [
      "Buka tab Liquidity Sweep",
      "Klik tombol Scan untuk analisis otomatis",
      "Lihat daftar equal highs/lows yang terdeteksi dan apakah sudah di-sweep",
    ],
    steps: [
      { step: "Identifikasi Equal Highs / Lows", detail: "Sistem mencari 2+ candle yang memiliki high atau low yang hampir sama. Ini adalah 'pool of liquidity' — tempat retail meletakkan SL mereka." },
      { step: "Tunggu Sweep Event", detail: "Saat candle menembus level equal high/low tersebut (apalagi dengan wick panjang), itu adalah SWEEP signal." },
      { step: "Konfirmasi dengan displacement", detail: "Setelah sweep, tunggu 1–2 candle yang bergerak kuat berlawanan arah. Ini konfirmasi bahwa sweep sudah selesai." },
      { step: "Entry setelah konfirmasi", detail: "Entry searah dengan displacement. SL di luar level yang di-sweep. Target: opposite liquidity pool atau FVG." },
    ],
    rules: [
      "✅ Entry SETELAH sweep selesai, bukan saat sedang terjadi",
      "✅ Konfirmasi dengan displacement candle (candle kuat berlawanan arah)",
      "✅ Paling powerful saat terjadi di dalam Killzone",
      "❌ Jangan entry saat harga MASIH di bawah equal low (mungkin belum selesai sweep)",
      "❌ Jangan asumsikan setiap break adalah sweep — tunggu konfirmasi",
    ],
    example: "ETH punya Equal Lows di $3,200 (terbentuk 3 candle terakhir). Harga tiba-tiba drop ke $3,188 dengan wick panjang, lalu close di $3,215. Ini SWEEP dari equal low. Langsung cari BUY setup di FVG atau OB terdekat di atas $3,200.",
    dontDo: ["Entry saat candle masih menembus level", "Ignore displacement setelah sweep", "Trade sweep di waktu ASIA (false sweep tinggi)"],
  },
  {
    id: "ob-strength",
    icon: "🧱",
    name: "Order Block Strength Meter",
    tagline: "Cari level di mana institusi pernah taruh order besar",
    color: "#f59e0b",
    what: "Order Block (OB) adalah candle terakhir yang bergerak berlawanan arah sebelum displacement besar terjadi. Ini adalah level di mana institusi menempatkan order mereka. Price sering kembali ke OB untuk 'mengisi' sisa order tersebut.",
    why: "Support & Resistance biasa hanyalah garis horizontal. OB adalah zone dengan ALASAN yang jelas — di situlah institusi menaruh order nyata. Hasilnya jauh lebih reliable daripada S/R biasa.",
    how: [
      "Buka tab OB Strength",
      "Pilih simbol dan timeframe",
      "Klik Scan untuk deteksi OB otomatis dengan skor kekuatan",
    ],
    steps: [
      { step: "Deteksi OB Formation", detail: "Sistem mencari candle terakhir yang berlawanan dengan displacement besar. Bullish OB = candle merah terakhir sebelum naik tajam. Bearish OB = candle hijau terakhir sebelum turun tajam." },
      { step: "Baca Strength Score (0–100)", detail: "Semakin tinggi skor, semakin powerful OB tersebut. Faktor: volume (tinggi = bagus), ukuran displacement, apakah masih fresh (belum pernah disentuh)." },
      { step: "Grade A–F", detail: "Grade A+ / A = Trade ini. Grade B = Valid tapi hati-hati. Grade C = Kecil kemungkinan berhasil. Grade F = Skip." },
      { step: "Entry di OB zone", detail: "Tunggu price kembali ke area OB (high–low candle OB). Entry di 50%–100% dari body OB. SL di luar OB. TP di opposite swing." },
    ],
    rules: [
      "✅ Hanya trade OB yang masih FRESH (belum pernah disentuh balik)",
      "✅ OB terkuat adalah yang terbentuk dari displacement terbesar",
      "✅ Kombinasikan OB + PD Zone + Killzone = A+ setup",
      "❌ OB yang sudah di-mitigasi (price sudah kembali dan melewatinya) → tidak valid lagi",
      "❌ Jangan entry OB yang terlalu jauh dari harga sekarang",
    ],
    example: "BTC punya Bullish OB di $62,400–$62,800 dengan strength 87 (Grade A). Harga saat ini $65,000. Price turun ke $62,600 (masuk OB zone) dalam London Killzone. Ini setup A+: entry BUY di $62,600, SL di $62,300 (bawah OB), TP di $66,000.",
    dontDo: ["Trade OB yang sudah di-mitigasi", "Ignore strength score — OB lemah sering gagal", "Entry OB tanpa konfirmasi Killzone"],
  },
  {
    id: "fvg-breaker",
    icon: "⬜",
    name: "FVG + Breaker Block",
    tagline: "Temukan 'lubang' di chart yang pasti akan diisi price",
    color: "#6366f1",
    what: "FVG (Fair Value Gap) adalah ketidakseimbangan antara pembeli dan penjual — 'lubang' yang terbentuk saat harga bergerak terlalu cepat. Price SELALU kembali mengisi lubang ini. Breaker Block adalah OB yang sudah gagal — area ini berbalik peran menjadi resistance/support kuat.",
    why: "FVG adalah magnet harga paling reliable di ICT methodology. Setiap kali ada FVG yang belum terisi, price punya 'kewajiban' untuk kembali ke sana. Ini bukan teori — ini adalah mekanika market yang terjadi berulang kali.",
    how: [
      "Buka tab FVG + Breaker",
      "Klik 'Scan FVG + Breakers'",
      "Lihat FVG Cards dan klik untuk expand detail + entry zone",
    ],
    steps: [
      { step: "Cara membaca FVG Card", detail: "Setiap card menampilkan: Gap Low/High (zone FVG), CE Level (50% = entry terbaik), ATR Multiplier (lebih besar = lebih kuat), Status (Fresh = terbaik), Strength 0–100." },
      { step: "CE Level = Entry Terbaik", detail: "CE (Consequent Encroachment) adalah titik tengah dari FVG. Saat price mencapai CE, ini adalah titik masuk paling presisi. Stop loss di bawah gap low (Bullish FVG)." },
      { step: "ICT Setup Score", detail: "Lihat GradeRing di pojok kanan. A+ = semua konfluens ada, masuk dengan confidence. WAIT = terlalu sedikit konfluens, tunggu dulu." },
      { step: "Breaker Block = Bekas OB yang Gagal", detail: "Saat OB di-break habis oleh price, OB itu jadi Breaker. Saat price pullback ke Breaker → entry berlawanan arah break awal. Setup dengan RR paling tinggi (1:5+)." },
    ],
    rules: [
      "✅ FVG FRESH = belum pernah disentuh = entry terbaik",
      "✅ Institutional FVG (>1.5x ATR) = magnet paling kuat",
      "✅ FVG Stack (2+ FVG overlap) = zona paling kuat di chart",
      "❌ FVG yang sudah FILLED 100% = tidak berlaku lagi",
      "❌ IFVG (Inverted) = FVG yang sudah dibalik — artinya berlawanan sekarang",
    ],
    example: "BTC punya Bullish FVG di $63,000–$63,800 (CE = $63,400). Status FRESH. Strength 82. Price saat ini $65,500. Dalam NY Open Killzone, price turun ke $63,450 (tepat di CE). Setup IDEAL: BUY di $63,400, SL di $62,900, TP1 di $65,500, TP2 di $67,000. R:R = 1:3.",
    dontDo: ["Entry FVG saat FILLED", "Ignore ICT Setup Score — jangan trade WAIT grade", "Miss Stacked FVGs — itu zone terkuat"],
  },
  {
    id: "position",
    icon: "⚖️",
    name: "Position Sizing Calculator",
    tagline: "Berapa banyak yang aman untuk ditaruhkan?",
    color: "#a78bfa",
    what: "Position Sizing Calculator menghitung berapa besar posisi yang optimal berdasarkan risiko yang ingin kamu ambil, ukuran akun, dan setup kamu. Menggunakan Kelly Criterion untuk optimalkan antara pertumbuhan dan keamanan akun.",
    why: "Lebih dari 70% trader yang profit pada akhirnya kehilangan akun mereka karena TERLALU BESAR posisi. Bukan karena analisis salah — tapi karena tidak ada money management. Calculator ini mencegah hal itu.",
    how: [
      "Buka tab Position Sizing",
      "Masukkan ukuran akun, risk % yang diinginkan, dan harga entry/SL",
      "Sistem menghitung ukuran posisi optimal secara otomatis",
    ],
    steps: [
      { step: "Masukkan Account Size", detail: "Total modal trading kamu dalam USD. Contoh: $10,000." },
      { step: "Set Risk Per Trade", detail: "Rekomendasi: 1% per trade untuk pemula, maks 2% untuk yang sudah berpengalaman. Dengan 1% risk, kamu perlu 100 trade loss berturut-turut untuk bankrupt — hampir mustahil." },
      { step: "Masukkan Entry & Stop Loss", detail: "Dari setup kamu (FVG atau OB), tentukan entry dan SL. Sistem menghitung otomatis: Position Size = (Account × Risk%) / (Entry - SL)." },
      { step: "Baca Kelly Criterion", detail: "Kelly fraction = berapa % optimal dari akun yang seharusnya di-risk berdasarkan win rate dan R:R historis kamu. Quarter Kelly (25% dari full Kelly) adalah rekomendasi praktis." },
    ],
    rules: [
      "✅ Maks risk 1–2% per trade",
      "✅ Gunakan Quarter Kelly sebagai batas atas ukuran posisi",
      "✅ Jika R:R kurang dari 1:1.5, skip trade tersebut",
      "❌ Jangan pernah risk lebih dari 5% dalam satu trade",
      "❌ Jangan tambah posisi saat losing (averaging down)",
      "❌ Jangan trade jika tidak bisa menghitung SL dengan jelas",
    ],
    example: "Akun $10,000. Risk 1% = $100 risk per trade. Entry BUY di $63,400. SL di $62,900. Jarak SL = $500. Position Size = $100 / $500 = 0.2 BTC. TP di $65,500. Profit potential = $420 (4.2R). Ini setup dengan RR baik.",
    dontDo: ["Trade tanpa menghitung position size dulu", "Risk lebih dari 2% karena 'yakin'", "Ignore R:R — ambil trade dengan R:R 1:0.5"],
  },
];

/* ── Step indicator ── */
function StepBadge({ n, color }: { n: number; color: string }) {
  return (
    <div style={{ width:28, height:28, borderRadius:"50%", flexShrink:0, background:`${color}20`, border:`2px solid ${color}40`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:"0.7rem", fontWeight:900, color }}>
      {n}
    </div>
  );
}

/* ── Tool Guide Card ── */
function ToolGuide({ tool, active, onSelect }: { tool: Tool; active: boolean; onSelect: () => void }) {
  return (
    <button onClick={onSelect} style={{
      display:"flex", alignItems:"center", gap:10,
      padding:"10px 14px", borderRadius:10, cursor:"pointer", width:"100%", textAlign:"left",
      background: active ? `${tool.color}15` : "rgba(255,255,255,0.02)",
      border:`1px solid ${active ? `${tool.color}40` : "rgba(255,255,255,0.06)"}`,
      transition:"all 0.2s",
    }}>
      <span style={{ fontSize:"1.2rem" }}>{tool.icon}</span>
      <div>
        <div style={{ fontSize:"0.78rem", fontWeight:800, color: active ? tool.color : "var(--text-secondary)" }}>{tool.name}</div>
        <div style={{ fontSize:"0.62rem", color:"var(--text-muted)" }}>{tool.tagline}</div>
      </div>
    </button>
  );
}

/* ── Main Page ── */
export default function GuideProPage() {
  const [activeTool, setActiveTool] = useState<ToolId>("killzone");
  const tool = TOOLS.find(t => t.id === activeTool)!;

  return (
    <MainLayout>
      {/* Header */}
      <div style={{ marginBottom:28 }}>
        <div style={{ display:"flex", alignItems:"center", gap:14, marginBottom:8 }}>
          <div style={{ width:42, height:42, borderRadius:12, background:"linear-gradient(135deg,#6366f1,#a78bfa)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:"1.2rem", boxShadow:"0 0 20px rgba(99,102,241,0.3)", border:"1px solid rgba(255,255,255,0.1)" }}>
            📚
          </div>
          <div>
            <h1 style={{ fontFamily:"'Outfit',sans-serif", fontSize:"1.8rem", fontWeight:900, letterSpacing:"-0.04em", margin:0, background:"linear-gradient(135deg,#fff 30%,#94a3b8)", WebkitBackgroundClip:"text", WebkitTextFillColor:"transparent" }}>
              Panduan Pro Tools
            </h1>
            <p style={{ color:"var(--text-muted)", fontSize:"0.8rem", margin:0, marginTop:4 }}>
              Pelajari cara kerja setiap tool sebelum menggunakannya · ICT Methodology
            </p>
          </div>
        </div>
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"280px 1fr", gap:24, alignItems:"start" }}>

        {/* ── Sidebar: tool list ── */}
        <div style={{ display:"flex", flexDirection:"column", gap:6, position:"sticky", top:20 }}>
          <div style={{ fontSize:"0.6rem", fontWeight:800, color:"var(--text-muted)", textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:4, paddingLeft:4 }}>Sprint 1 Tools</div>
          {TOOLS.map(t => (
            <ToolGuide key={t.id} tool={t} active={activeTool === t.id} onSelect={() => setActiveTool(t.id)} />
          ))}

          {/* Quick links */}
          <div style={{ marginTop:16, padding:"14px 16px", borderRadius:12, background:"rgba(99,102,241,0.06)", border:"1px solid rgba(99,102,241,0.15)" }}>
            <div style={{ fontSize:"0.7rem", fontWeight:800, color:"#6366f1", marginBottom:8 }}>ICT Checklist A+ Setup</div>
            {[
              "✅ Dalam Killzone (London/NY)",
              "✅ Price di Discount/Premium zone",
              "✅ Ada Liquidity Sweep terkonfirmasi",
              "✅ FVG atau OB masih FRESH",
              "✅ R:R minimal 1:2",
              "✅ Risk max 1–2% akun",
            ].map((item, i) => (
              <div key={i} style={{ fontSize:"0.65rem", color:"var(--text-muted)", marginBottom:4 }}>{item}</div>
            ))}
          </div>
        </div>

        {/* ── Main Content ── */}
        <div style={{ display:"flex", flexDirection:"column", gap:16 }}>

          {/* Tool header */}
          <div style={{ padding:"20px 24px", borderRadius:16, background:`${tool.color}08`, border:`1px solid ${tool.color}25` }}>
            <div style={{ display:"flex", alignItems:"flex-start", gap:14 }}>
              <div style={{ fontSize:"2.5rem", lineHeight:1 }}>{tool.icon}</div>
              <div>
                <h2 style={{ margin:0, fontSize:"1.3rem", fontWeight:900, color:"#fff" }}>{tool.name}</h2>
                <div style={{ fontSize:"0.85rem", color:tool.color, fontWeight:700, marginTop:4 }}>{tool.tagline}</div>
              </div>
            </div>
          </div>

          {/* WHAT */}
          <div style={{ padding:"18px 20px", borderRadius:14, background:"rgba(255,255,255,0.02)", border:"1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ fontSize:"0.65rem", fontWeight:800, color:`${tool.color}`, textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:8 }}>Apa itu?</div>
            <p style={{ fontSize:"0.85rem", color:"var(--text-secondary)", lineHeight:1.8, margin:0 }}>{tool.what}</p>
          </div>

          {/* WHY */}
          <div style={{ padding:"18px 20px", borderRadius:14, background:`${tool.color}06`, border:`1px solid ${tool.color}18` }}>
            <div style={{ fontSize:"0.65rem", fontWeight:800, color:tool.color, textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:8 }}>Mengapa penting?</div>
            <p style={{ fontSize:"0.85rem", color:"var(--text-secondary)", lineHeight:1.8, margin:0 }}>💡 {tool.why}</p>
          </div>

          {/* HOW TO USE */}
          <div style={{ padding:"18px 20px", borderRadius:14, background:"rgba(255,255,255,0.02)", border:"1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ fontSize:"0.65rem", fontWeight:800, color:tool.color, textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:14 }}>Cara menggunakan</div>
            <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
              {tool.how.map((h, i) => (
                <div key={i} style={{ display:"flex", alignItems:"flex-start", gap:10 }}>
                  <div style={{ width:22, height:22, borderRadius:6, flexShrink:0, background:`${tool.color}20`, border:`1px solid ${tool.color}40`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:"0.65rem", fontWeight:900, color:tool.color }}>{i+1}</div>
                  <div style={{ fontSize:"0.78rem", color:"var(--text-secondary)", paddingTop:2, lineHeight:1.5 }}>{h}</div>
                </div>
              ))}
            </div>
          </div>

          {/* STEPS */}
          <div style={{ padding:"18px 20px", borderRadius:14, background:"rgba(255,255,255,0.02)", border:"1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ fontSize:"0.65rem", fontWeight:800, color:tool.color, textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:14 }}>Step-by-step workflow</div>
            <div style={{ display:"flex", flexDirection:"column", gap:12, position:"relative" }}>
              {/* Vertical line */}
              <div style={{ position:"absolute", left:14, top:28, bottom:0, width:1, background:`${tool.color}25`, zIndex:0 }} />
              {tool.steps.map((s, i) => (
                <div key={i} style={{ display:"flex", gap:14, position:"relative", zIndex:1 }}>
                  <StepBadge n={i+1} color={tool.color} />
                  <div style={{ background:"rgba(255,255,255,0.02)", border:`1px solid rgba(255,255,255,0.06)`, borderRadius:10, padding:"10px 14px", flex:1 }}>
                    <div style={{ fontSize:"0.75rem", fontWeight:800, color:"#fff", marginBottom:5 }}>{s.step}</div>
                    <div style={{ fontSize:"0.72rem", color:"var(--text-muted)", lineHeight:1.6 }}>{s.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* RULES */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 }}>
            <div style={{ padding:"16px 18px", borderRadius:14, background:"rgba(16,185,129,0.05)", border:"1px solid rgba(16,185,129,0.15)" }}>
              <div style={{ fontSize:"0.65rem", fontWeight:800, color:"#10b981", textTransform:"uppercase", marginBottom:10 }}>Rules — Lakukan ini</div>
              {tool.rules.filter(r => r.startsWith("✅")).map((r, i) => (
                <div key={i} style={{ fontSize:"0.72rem", color:"var(--text-muted)", marginBottom:6, lineHeight:1.5 }}>{r}</div>
              ))}
            </div>
            <div style={{ padding:"16px 18px", borderRadius:14, background:"rgba(239,68,68,0.05)", border:"1px solid rgba(239,68,68,0.15)" }}>
              <div style={{ fontSize:"0.65rem", fontWeight:800, color:"#ef4444", textTransform:"uppercase", marginBottom:10 }}>Jangan lakukan ini</div>
              {tool.rules.filter(r => r.startsWith("❌")).map((r, i) => (
                <div key={i} style={{ fontSize:"0.72rem", color:"var(--text-muted)", marginBottom:6, lineHeight:1.5 }}>{r}</div>
              ))}
            </div>
          </div>

          {/* REAL EXAMPLE */}
          <div style={{ padding:"18px 20px", borderRadius:14, background:"rgba(99,102,241,0.06)", border:"1px solid rgba(99,102,241,0.2)" }}>
            <div style={{ fontSize:"0.65rem", fontWeight:800, color:"#6366f1", textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:10 }}>Contoh Nyata</div>
            <div style={{ fontSize:"0.78rem", color:"var(--text-secondary)", lineHeight:1.8 }}>
              {tool.example}
            </div>
          </div>

          {/* DONT DO */}
          <div style={{ padding:"16px 18px", borderRadius:14, background:"rgba(245,158,11,0.05)", border:"1px solid rgba(245,158,11,0.2)" }}>
            <div style={{ fontSize:"0.65rem", fontWeight:800, color:"#f59e0b", textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:10 }}>Kesalahan Umum — Hindari!</div>
            <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
              {tool.dontDo.map((d, i) => (
                <div key={i} style={{ display:"flex", alignItems:"flex-start", gap:8 }}>
                  <span style={{ color:"#f59e0b", fontWeight:900, flexShrink:0 }}>⚠</span>
                  <div style={{ fontSize:"0.72rem", color:"var(--text-muted)", lineHeight:1.5 }}>{d}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Navigation buttons */}
          <div style={{ display:"flex", justifyContent:"space-between", marginTop:4 }}>
            {(() => {
              const idx = TOOLS.findIndex(t => t.id === activeTool);
              const prev = TOOLS[idx - 1];
              const next = TOOLS[idx + 1];
              return (
                <>
                  <div>
                    {prev && (
                      <button onClick={() => setActiveTool(prev.id)} style={{ padding:"9px 18px", borderRadius:9, background:"rgba(255,255,255,0.04)", border:"1px solid rgba(255,255,255,0.08)", color:"var(--text-muted)", fontSize:"0.75rem", fontWeight:700, cursor:"pointer" }}>
                        ← {prev.icon} {prev.name}
                      </button>
                    )}
                  </div>
                  <div>
                    {next && (
                      <button onClick={() => setActiveTool(next.id)} style={{ padding:"9px 18px", borderRadius:9, background:`${next.color}15`, border:`1px solid ${next.color}35`, color:next.color, fontSize:"0.75rem", fontWeight:700, cursor:"pointer" }}>
                        {next.icon} {next.name} →
                      </button>
                    )}
                  </div>
                </>
              );
            })()}
          </div>

        </div>
      </div>
    </MainLayout>
  );
}
