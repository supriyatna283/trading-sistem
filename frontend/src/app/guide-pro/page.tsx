"use client";

import MainLayout from "@/components/layout/MainLayout";
import { useState } from "react";
import Link from "next/link";

/* ── Types ── */
type ToolId =
  | "sop-timeframe"
  | "workflow-pro"
  | "ai-copilot"
  | "live-scanner"
  | "ict-confluence"
  | "killzone"
  | "pd-zones"
  | "sweep"
  | "ob-strength"
  | "fvg-breaker"
  | "position";

interface Tool {
  id: ToolId;
  category: "SOP & Pedoman Utama" | "AI & Scanner Command" | "ICT & Smart Money Tools";
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
    id: "sop-timeframe",
    category: "SOP & Pedoman Utama",
    icon: "🏆",
    name: "Pedoman Timeframe (1H + 15M)",
    tagline: "Standar emas pemilihan timeframe untuk akurasi sinyal tertinggi",
    color: "#f59e0b",
    what: "Kombinasi Timeframe 1H (1 Jam) sebagai peta utama (dengan HTF otomatis 4H) dan 15M (15 Menit) sebagai sniper entry adalah standar emas (Sweet Spot) pada sistem Quant + ICT/SMC ini.",
    why: "Di pasar kripto, timeframe di bawah 15m (1m/5m) penuh dengan noise dan manipulasi wick (jarum candle) yang sering memicu sinyal palsu. Di timeframe 1H, Order Block (OB), Fair Value Gap (FVG), dan Volume Profile (POC/VAH/VAL) benar-benar dihormati oleh algoritma institusi, sementara jarak Stop Loss (0.8%–2.2%) sangat ideal agar rasio R:R 1:2.5 tidak habis termakan trading fee.",
    how: [
      "Intraday / Day Trading (Paling Direkomendasikan 🏆): Gunakan 1H di Live Scanner & ICT Confluence (HTF otomatis 4H), lalu gunakan 15M di Chart untuk konfirmasi entry.",
      "Active Session / Scalping (Khusus Jam Killzone): Gunakan 15M di Scanner (HTF otomatis 1H) dan 15M/5M untuk eksekusi HANYA saat London Open (14:00–17:00 WIB) atau NY Open (19:00–22:00 WIB).",
      "Swing Trading (Sibuk Bekerja / Santai): Gunakan 4H di Scanner & ICT Confluence (HTF otomatis 1D) dan 1H untuk memasang limit order (tahan posisi 2–7 hari).",
    ],
    steps: [
      {
        step: "Langkah 1 — Kunci Peta Besar di Timeframe 1H",
        detail: "Buka Pro Tools → Live Scanner dan pilih tombol 1H. Sistem otomatis memeriksa keselarasan struktur 1D, 4H, dan 1H. Pilih koin berstatus Grade A+ atau VALID.",
      },
      {
        step: "Langkah 2 — Validasi Zona Discount / Premium di 1H",
        detail: "Klik ⚡ ICT Detail pada koin tersebut (pastikan Global Timeframe di 1h). Pastikan sinyal BUY berada di zona DISCOUNT (<38%) atau SELL berada di zona PREMIUM (>62%).",
      },
      {
        step: "Langkah 3 — Jalankan DeepSeek AI di Chart 1H",
        detail: "Buka halaman Charts (/charts) pada timeframe 1H. Baca 5 bagian laporan DeepSeek-R1 untuk mengunci level Volume Profile (POC, VAH, VAL) dan titik invalidasi mutlak.",
      },
      {
        step: "Langkah 4 — Tajamkan Entry (Sniper) di 15M",
        detail: "Saat harga sudah masuk ke Entry Zone 1H, turunkan chart ke 15M. Tunggu konfirmasi pantulan (Pin Bar, Liquidity Sweep, atau CHoCH kecil) agar mendapat Stop Loss paling tipis dan R:R maksimal.",
      },
    ],
    rules: [
      "✅ Gunakan 1H sebagai patokan utama sehari-hari (Sweet Spot akurasi & R:R)",
      "✅ Gunakan rumus 2-Timeframe: Analisis & cari setup di 1H → Eksekusi presisi di 15M",
      "✅ Gunakan 4H jika Anda sibuk dan hanya bisa cek chart pagi & malam",
      "❌ Jangan gunakan 5m sendirian tanpa melihat bias 1H",
      "❌ Hindari timeframe kecil (5m/15m) saat sesi Asia Dead Zone / NY Lunch atau saat ADX < 18",
    ],
    example: "Di Live Scanner 1H, ETHUSDT muncul sebagai Grade A+ (BUY / LONG, Score 76, Discount + Bull FVG + 1 Bull OB, R:R 1:2.5). Anda klik 📈 Chart, cek analisis DeepSeek AI di 1H, lalu pindah ke 15M saat harga menyentuh zona Entry untuk masuk posisi setelah muncul candle pantulan.",
    dontDo: [
      "Menggunakan timeframe 5m di luar jam Killzone (hampir semua breakout di jam sepi adalah jebakan Judas Swing)",
      "Melawan arah HTF (misal memaksa BUY di 15m padahal 1D, 4H, dan 1H semuanya BEARISH tanpa ada Liquidity Sweep)",
      "Berpindah-pindah timeframe untuk mencari pembenaran saat posisi sedang floating loss",
    ],
  },
  {
    id: "workflow-pro",
    category: "SOP & Pedoman Utama",
    icon: "🧭",
    name: "Alur Kerja 4 Langkah Pro Tools",
    tagline: "Urutan sistematis memakai 13 tab Pro Tools dari awal sampai eksekusi",
    color: "#10b981",
    what: "Halaman Pro Trading Tools (/pro-tools) memiliki 13 tab spesialis ICT & Smart Money. Agar efektif dan tidak membingungkan, gunakan urutan Top-Down 4 Langkah: (1) Live Scanner → (2) ICT Confluence & Multi-TF → (3) Bedah Array SMC → (4) Position Sizing & Alerts.",
    why: "Menganalisis puluhan koin satu per satu secara manual memakan waktu dan memicu kelelahan keputusan (decision fatigue). Dengan alur 4 langkah ini, Anda hanya menghabiskan waktu pada koin yang sudah terbukti memiliki probabilitas tinggi.",
    how: [
      "Atur Global Symbol & Timeframe (disarankan 1h) di bar kontrol paling atas halaman Pro Tools.",
      "Mulai dari tab Live Scanner untuk memilih kandidat koin Grade A+ / VALID.",
      "Gunakan tombol pintas 1-klik pada kartu Scanner (⚡ ICT Detail, 🔢 Pos Calc, 🔔 WA, 📈 Chart) untuk berpindah antar-tahap secara instan.",
    ],
    steps: [
      {
        step: "Tahap 1 — Saring Peluang di Tab 📡 Live Scanner",
        detail: "Cek banner Killzone di atas, pilih TF 1H dan filter ⚡ Ready. Pilih koin Grade A+ atau VALID yang sudah memiliki Trade Plan lengkap (Entry Zone, SL, TP1, TP2, R:R).",
      },
      {
        step: "Tahap 2 — Validasi Menyeluruh di Tab 🎯 ICT Confluence & 📊 Multi-TF",
        detail: "Klik ⚡ ICT Detail dari kartu Scanner. Periksa keselarasan 6 komponen ICT sekaligus (Killzone, P/D Zone, Sweep, OB, FVG, HTF Bias) dan pastikan Auto Trade Plan searah.",
      },
      {
        step: "Tahap 3 — Bedah Array Spesifik (Opsional bila butuh presisi ekstra)",
        detail: "Cek tab P/D Zones (pastikan di OTE 0.618–0.786), Sweep (cek apakah stop loss ritel sudah disapu), OB Strength (skor kualitas OB 0–100), FVG+Breaker (cek CE 50% level), serta Wyckoff & Options/Perps.",
      },
      {
        step: "Tahap 4 — Hitung Kontrak di Tab 🔢 Position & Pasang 🔔 Conditional Alerts",
        detail: "Klik tombol 🔢 Pos Calc pada kartu Scanner atau ICT Confluence. Masukkan modal ($) dan risiko (1%), lalu ambil angka Quantity/Leveraged Size yang aman sebelum membuka order.",
      },
    ],
    rules: [
      "✅ Selalu mulai dari Live Scanner (jangan menebak koin secara acak)",
      "✅ Pastikan minimal 2 dari 3 timeframe di tab Multi-TF (4H, 1H, 15M) searah",
      "✅ Wajib klik 🔢 Pos Calc untuk menghitung ukuran posisi sebelum entry",
      "❌ Jangan langsung entry tanpa mengecek lokasi harga di P/D Zone (Discount/Premium)",
      "❌ Jangan abaikan peringatan Funding Rate ekstrem di tab Options & Perps",
    ],
    example: "Buka Pro Tools → Live Scanner (1H) → Temukan SOLUSDT Grade VALID (SHORT, R:R 1:2.5) → Klik ⚡ ICT Detail untuk verifikasi Bearish FVG & Liquidity Sweep → Klik 🔢 Pos Calc (Modal $1,000, Risk 1% = posisi terukur otomatis) → Klik 📈 Chart untuk eksekusi.",
    dontDo: [
      "Membuka semua 13 tab secara acak tanpa urutan yang jelas",
      "Masuk posisi tanpa menghitung jumlah lot/kontrak di tab Position",
      "Mengabaikan sinyal HTF di pojok kanan atas bar Global Symbol",
    ],
  },
  {
    id: "ai-copilot",
    category: "AI & Scanner Command",
    icon: "🤖",
    name: "DeepSeek-R1 AI Chart Copilot",
    tagline: "Cara memakai asisten AI kuantitatif & SMC di halaman Charts",
    color: "#38bdf8",
    what: "DeepSeek-R1 AI Agent di halaman Charts (/charts) adalah analis kuantitatif & ICT real-time yang memadukan data Multi-Timeframe (1D/4H/1H/15M), EMA Stack (20/50/200), Volume Profile (POC/VAH/VAL), Fibonacci OTE, Order Block, FVG, Liquidity Sweep, Order Flow Whale, dan Makro menjadi 5 kartu laporan Bahasa Indonesia + fitur tanya jawab interaktif.",
    why: "Manusia sering melewatkan detail penting saat melihat chart (misalnya melihat sinyal BUY di RSI, tetapi lupa bahwa harga tepat di bawah resistance VAH atau ada Bearish Order Block di atas). DeepSeek-R1 memeriksa seluruh 20+ variabel tersebut secara objektif dalam hitungan detik.",
    how: [
      "Buka halaman Charts (/charts), lalu klik tombol 🤖 DeepSeek Agent di kanan atas.",
      "Klik ikon 🔑 di pojok kanan atas panel AI untuk menyimpan DeepSeek API Key Anda (cukup sekali).",
      "Gunakan 4 tab di dalam panel AI: ⚡ Setup (angka eksekusi & kalkulator lot), ◎ Score (checklist 8 konfluensi), 🌐 Macro (Whale detector & berita), dan 🧠 Analisis (laporan 5 bagian + chat).",
    ],
    steps: [
      {
        step: "1. Cek Tab ⚡ Setup & Garis Otomatis di Chart",
        detail: "Jika sinyal BUY/SELL, garis Entry Zone, Stop Loss, dan TP1–TP3 otomatis tergambar di chart. Jika sinyal WAIT, lihat kotak 'Level Referensi Kunci Saat Ini' (VAL/POC/VAH, VWAP, EMA, Fib).",
      },
      {
        step: "2. Cek Tab ◎ Score & 🌐 Macro (Whale Detector)",
        detail: "Pastikan skor konfluensi mendukung dan cek Whale Position Detector di tab Macro apakah transaksi institusi (>$50k) sedang dominan akumulasi (NET LONG) atau distribusi (NET SHORT).",
      },
      {
        step: "3. Baca 5 Kartu Laporan di Tab 🧠 Analisis",
        detail: "Klik tombol Lebarkan Panel (⇤) di kanan atas agar nyaman membaca: (01) Struktur & Volume Profile, (02) Konfluensi Fib OTE & SMC, (03) Rencana Eksekusi / Skenario Trigger, (04) Skenario Gagal & 3 Titik Invalidasi Mutlak, (05) Kesimpulan Eksekutif.",
      },
      {
        step: "4. Gunakan Tombol Quick Ask & Chat Interaktif",
        detail: "Klik tombol cepat (📍 Entry optimal?, 🎯 Target TP?, ⚠️ Kapan stop?, 📊 HTF Trend?) untuk langsung bertanya dengan 1 klik, atau ketik pertanyaan spesifik posisi Anda di kolom chat.",
      },
    ],
    rules: [
      "✅ Gunakan tombol Lebarkan Panel (⇤) saat membaca tab Analisis",
      "✅ Perhatikan Bagian 04 (3 level harga spesifik yang membatalkan setup secara mutlak)",
      "✅ Manfaatkan fitur Smart Cache: tidak perlu klik Refresh berulang-ulang jika candle belum berganti",
      "❌ Jangan langsung market order jika kesimpulan AI adalah WAIT — tunggu harga menyentuh level Trigger BUY/SELL yang disebutkan di Bagian 03",
      "❌ Jangan abaikan peringatan risiko makro/funding rate di Bagian 04",
    ],
    example: "Anda membuka HYPEUSDT 15M dan statusnya WAIT. Di tab Setup Anda melihat POC di $77.39 dan VAH di $78.65. Anda klik 'Buka Skenario Trigger BUY & SELL di Tab Analisis', lalu membaca di Bagian 03 syarat persis harga berapa yang harus di-reclaim atau di-reject sebelum boleh entry.",
    dontDo: [
      "Menekan tombol Refresh terus-menerus dalam 1 menit yang sama (membuang kuota token API secara percuma)",
      "Hanya melihat kata BUY/SELL tanpa membaca 3 titik invalidasi mutlak di Bagian 04",
      "Mengabaikan ketidakcocokan antara sinyal TF kecil dan tren 1D/4H",
    ],
  },
  {
    id: "live-scanner",
    category: "AI & Scanner Command",
    icon: "📡",
    name: "Institutional Live Scanner",
    tagline: "Memindai 24 pair paling likuid secara otomatis untuk mencari setup A+ & Valid",
    color: "#e879f9",
    what: "Live Scanner di tab pertama Pro Tools memindai 24 koin perpetual paling likuid secara paralel menggunakan mesin Hybrid Quant + ICT, lalu menyaring hanya koin yang memiliki tren jelas, lolos filter risiko, dan memiliki Trade Plan lengkap.",
    why: "Daripada membuka 24 chart satu per satu, Live Scanner merangkum kondisi pasar secara real-time (Market Pulse Strip: jumlah Ready Setups, rasio Long vs Short, dan rata-rata R:R) serta langsung menyajikan kotak Entry Zone, Stop Loss, TP1, dan TP2 di setiap kartu.",
    how: [
      "Buka Pro Tools → tab Live Scanner.",
      "Pilih timeframe scan (disarankan 1H untuk intraday atau 15M saat Killzone aktif).",
      "Gunakan filter ⚡ Ready untuk melihat koin yang siap dieksekusi, atau 📋 All Scanned untuk melihat koin watchlist beserta alasan kenapa belum valid.",
    ],
    steps: [
      {
        step: "Baca Market Pulse Strip di Atas",
        detail: "Lihat berapa koin yang berstatus Ready, berapa yang Grade A+ vs Valid, serta apakah pasar hari ini condong ke LONG atau SHORT (Directional Skew).",
      },
      {
        step: "Periksa Badge ICT & Kotak Trade Plan pada Kartu",
        detail: "Setiap kartu Ready menampilkan pill 🟢 LONG atau 🔴 SHORT, badge konfluensi searah (Discount OTE, Liq Sweep, Bull/Bear FVG, OB, BOS/CHoCH), serta angka Entry Zone, SL, TP1, dan TP2.",
      },
      {
        step: "Cek 6 Pilar Skor (STR, PA, SMC, VOL, TIM, RR)",
        detail: "Bar di bagian bawah kartu menunjukkan skor kekuatan 0–100 pada 6 pilar: Strength/HTF, Price Action, Smart Money, Volume, Timing, dan Risk:Reward.",
      },
      {
        step: "Eksekusi Cepat dengan 4 Tombol Aksi",
        detail: "Klik ⚡ ICT Detail untuk analisis mendalam, 🔢 Pos Calc untuk langsung memuat Entry/SL/TP ke kalkulator lot, 🔔 WA untuk kirim sinyal ke WhatsApp, atau 📈 Chart untuk buka chart.",
      },
    ],
    rules: [
      "✅ Prioritaskan koin dengan Grade A+ (Score >= 72) atau VALID (Score >= 48) dengan MTF: STRONG/MODERATE",
      "✅ Utamakan koin yang memiliki minimal 3 badge ICT (misal: Discount + Liq Sweep + Bull FVG)",
      "✅ Gunakan tombol 🔢 Pos Calc langsung dari kartu Scanner agar tidak salah ketik harga Entry/SL",
      "❌ Jangan memaksakan entry pada koin berstatus Watchlist/Filtered (misal karena Sideways atau Overbought RSI)",
      "❌ Jangan mengambil semua sinyal sekaligus — pilih 1 atau 2 koin dengan skor tertinggi saja",
    ],
    example: "Pada scan 1H, muncul 3 Ready Setups. ETHUSDT memiliki skor tertinggi (Grade A+, Score 76, 🟢 LONG, R:R 1:2.5, badge: Discount, Fib 0.382, Bull FVG, 1 Bull OB, BOS/CHoCH). Anda langsung klik 🔢 Pos Calc untuk hitung ukuran posisi dan pasang limit order di Entry Zone.",
    dontDo: [
      "Membuka posisi pada 5–6 koin secara bersamaan (korelasinya tinggi di kripto, sehingga risiko berlipat ganda)",
      "Mengabaikan alasan penolakan pada koin yang ada di tab All Scanned",
    ],
  },
  {
    id: "ict-confluence",
    category: "AI & Scanner Command",
    icon: "🎯",
    name: "ICT Confluence Dashboard",
    tagline: "Ruang kendali 6 sinyal ICT dalam satu layar + Auto Trade Plan",
    color: "#10b981",
    what: "ICT Confluence Dashboard menggabungkan seluruh 6 mesin ICT (Killzone, Premium/Discount & OTE, Liquidity Sweep, Order Block, FVG/Breaker, dan HTF Bias) menjadi satu skor terpadu lengkap dengan Auto Trade Plan yang otomatis menyesuaikan arah BUY atau SELL.",
    why: "Trading hanya berdasarkan 1 indikator (misal hanya FVG saja) sering kali gagal. Ketika FVG berada di dalam zona Discount OTE, searah HTF, terjadi setelah Liquidity Sweep, dan berada di jam Killzone, probabilitas keberhasilannya melonjak drastis.",
    how: [
      "Pilih koin dari Global Symbol atau klik ⚡ ICT Detail dari Live Scanner.",
      "Lihat Grade Ring (A+ / A / B / C / WAIT) dan bias utama di bagian atas dashboard.",
      "Periksa kotak Auto Trade Plan (Entry, Stop Loss, TP1, TP2, dan R:R) lalu klik 🔢 Hitung Lot / Pos Size.",
    ],
    steps: [
      {
        step: "Periksa Skor & Layer Konfluensi Aktif",
        detail: "Lihat berapa banyak dari 6 layer ICT yang menyala hijau dan searah dengan bias utama.",
      },
      {
        step: "Validasi Geometri Auto Trade Plan",
        detail: "Untuk sinyal BUY, pastikan SL berada di bawah Entry dan TP1/TP2 berada di atas Entry. Untuk sinyal SELL, pastikan SL berada di atas Entry dan TP1/TP2 berada di bawah Entry.",
      },
      {
        step: "Kirim ke Kalkulator Posisi atau WhatsApp",
        detail: "Klik tombol 🔢 Hitung Lot / Pos Size untuk memuat rencana trading ke tab Position, atau klik 🔔 Kirim WA Alert untuk menyimpan catatan sinyal ke WhatsApp Anda.",
      },
    ],
    rules: [
      "✅ Eksekusi penuh hanya saat Grade A+ atau A",
      "✅ Kurangi risiko setengahnya (misal 0.5% akun) jika Grade B",
      "❌ Jangan entry jika status dashboard masih WAIT / NEUTRAL",
    ],
    example: "Pada AVAXUSDT 1H, ICT Confluence menampilkan Grade A (BUY), dengan konfluensi aktif: Discount Zone + Bullish FVG + Bullish OB + HTF Bullish. Auto Trade Plan menampilkan Entry, SL di bawah struktur, dan TP1/TP2 dengan R:R 1:2 dan 1:3.",
    dontDo: [
      "Melawan arah bias utama yang ditampilkan oleh konsensus 6 komponen ICT",
      "Mengubah-ubah Stop Loss menjadi terlalu sempit di luar batas struktur/ATR",
    ],
  },
  {
    id: "killzone",
    category: "ICT & Smart Money Tools",
    icon: "⏰",
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
      { step: "ASIA (00:00–07:00 UTC / 07:00–14:00 WIB)", detail: "JANGAN TRADE. Hanya observasi. Catat harga tertinggi (Asia High) dan terendah (Asia Low) — ini akan jadi target sweep nanti." },
      { step: "LONDON OPEN (07:00–10:00 UTC / 14:00–17:00 WIB)", detail: "Killzone pertama. Market sering sweep Asia High ATAU Low secara palsu (Judas Swing) sebelum berbalik ke arah sebenarnya." },
      { step: "NEW YORK OPEN (12:00–15:00 UTC / 19:00–22:00 WIB)", detail: "Killzone paling kuat. Konfirmasi atau pembalikan dari arah London. Setup terbaik untuk entry." },
      { step: "NY LUNCH & CLOSE (17:00+ UTC)", detail: "Volume turun drastis. Hindari entry baru. Close position jika tidak nyaman hold overnight." },
    ],
    rules: [
      "✅ Entry HANYA di dalam Killzone",
      "✅ Jika tidak ada killzone aktif = gunakan limit order di zona OB/FVG 1H",
      "❌ Jangan scalping saat ASIA Dead Zone — itu jebakan",
      "❌ Jangan overtrade saat weekend — likuiditas tipis, manipulasi tinggi",
    ],
    example: "Kamu lihat harga Bitcoin sweep Asia Low di jam 07:15 UTC (14:15 WIB — London Open). Ini sinyal: Smart Money ambil likuiditas di bawah, kemungkinan besar akan naik. TUNGGU konfirmasi, baru entry BUY.",
    dontDo: ["Trading jam 2 pagi karena 'bosan'", "Masuk market order saat DEAD ZONE", "Ignore session overlap"],
  },
  {
    id: "pd-zones",
    category: "ICT & Smart Money Tools",
    icon: "📊",
    name: "Premium / Discount Zones",
    tagline: "Beli murah, jual mahal — seperti yang institusi lakukan",
    color: "#3b82f6",
    what: "PD Zone adalah konsep bahwa market selalu bergerak dari zona PREMIUM (mahal) ke DISCOUNT (murah) dan sebaliknya. Institusi SELALU beli di Discount dan jual di Premium — tidak pernah sebaliknya.",
    why: "Retail trader sering beli di puncak dan jual di bawah — kebalikan dari institusi. Dengan mengetahui apakah price sekarang di Premium atau Discount, kamu bisa masuk searah dengan Smart Money.",
    how: [
      "Buka tab P/D Zones",
      "Masukkan simbol (contoh: BTCUSDT) dan timeframe HTF (1d atau 4h)",
      "Lihat posisi harga saat ini terhadap Equilibrium (50%) dan zona OTE (61.8%–78.6%)",
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
    dontDo: ["BUY saat price di atas 62% range", "Gunakan LTF 5m untuk PD Zone reference utama", "Ignore HTF bias"],
  },
  {
    id: "sweep",
    category: "ICT & Smart Money Tools",
    icon: "🌊",
    name: "Liquidity Sweep Detector",
    tagline: "Deteksi kapan Smart Money 'berburu' stop loss kamu",
    color: "#ef4444",
    what: "Liquidity Sweep adalah saat Smart Money sengaja mendorong harga melewati level penting (high/low, equal highs/lows) untuk trigger stop loss retail trader — mengambil 'likuiditas' — sebelum berbalik ke arah sebenarnya.",
    why: "Stop loss kamu adalah ORDER BUY/SELL bagi institusi. Mereka BUTUH volume besar untuk mengisi posisi mereka. Dengan mendeteksi sweep, kamu bisa masuk SETELAH institusi selesai 'berburu' dan ikut arah sebenarnya.",
    how: [
      "Buka tab Sweep",
      "Sistem otomatis memindai Equal Highs (BSL) dan Equal Lows (SSL)",
      "Lihat apakah sweep sudah Confirmed (ditutup kembali di dalam range)",
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
      "❌ Jangan asumsikan setiap break adalah sweep — tunggu konfirmasi close candle",
    ],
    example: "ETH punya Equal Lows di $3,200 (terbentuk 3 candle terakhir). Harga tiba-tiba drop ke $3,188 dengan wick panjang, lalu close di $3,215. Ini SWEEP dari equal low. Langsung cari BUY setup di FVG atau OB terdekat di atas $3,200.",
    dontDo: ["Entry saat candle masih menembus level", "Ignore displacement setelah sweep", "Trade sweep di waktu ASIA (false sweep tinggi)"],
  },
  {
    id: "ob-strength",
    category: "ICT & Smart Money Tools",
    icon: "🧱",
    name: "Order Block Strength Meter",
    tagline: "Cari level di mana institusi pernah taruh order besar",
    color: "#f59e0b",
    what: "Order Block (OB) adalah candle terakhir yang bergerak berlawanan arah sebelum displacement besar terjadi. Ini adalah level di mana institusi menempatkan order mereka. Price sering kembali ke OB untuk 'mengisi' sisa order tersebut.",
    why: "Support & Resistance biasa hanyalah garis horizontal. OB adalah zone dengan ALASAN yang jelas — di situlah institusi menaruh order nyata. Hasilnya jauh lebih reliable daripada S/R biasa.",
    how: [
      "Buka tab OB Strength",
      "Pilih simbol dan timeframe (disarankan 1H atau 4H)",
      "Lihat daftar Bullish OB & Bearish OB yang masih aktif beserta skor kekuatannya",
    ],
    steps: [
      { step: "Deteksi OB Formation", detail: "Sistem mencari candle terakhir yang berlawanan dengan displacement besar. Bullish OB = candle merah terakhir sebelum naik tajam. Bearish OB = candle hijau terakhir sebelum turun tajam." },
      { step: "Baca Strength Score (0–100)", detail: "Semakin tinggi skor, semakin powerful OB tersebut. Faktor: volume (tinggi = bagus), ukuran displacement, apakah masih fresh (belum pernah disentuh)." },
      { step: "Grade A–F", detail: "Grade A+ / A = Trade ini. Grade B = Valid tapi hati-hati. Grade C = Kecil kemungkinan berhasil. Grade F = Skip." },
      { step: "Entry di OB zone", detail: "Tunggu price kembali ke area OB (high–low candle OB). Entry di 50%–100% dari body OB. SL di luar OB. TP di opposite swing." },
    ],
    rules: [
      "✅ Hanya trade OB yang masih FRESH (belum pernah ditembus/invalidated)",
      "✅ OB terkuat adalah yang terbentuk dari displacement terbesar",
      "✅ Kombinasikan OB + PD Zone + Killzone = A+ setup",
      "❌ OB yang sudah ditembus habis (invalidated) → jangan dijadikan tempat entry OB lagi",
      "❌ Jangan entry OB yang terlalu jauh (>3% dari harga sekarang)",
    ],
    example: "BTC punya Bullish OB di $62,400–$62,800 dengan strength 87 (Grade A). Harga saat ini $65,000. Price turun ke $62,600 (masuk OB zone) dalam London Killzone. Ini setup A+: entry BUY di $62,600, SL di $62,300 (bawah OB), TP di $66,000.",
    dontDo: ["Trade OB yang sudah di-mitigasi habis", "Ignore strength score — OB lemah sering gagal", "Entry OB tanpa konfirmasi Killzone"],
  },
  {
    id: "fvg-breaker",
    category: "ICT & Smart Money Tools",
    icon: "⬜",
    name: "FVG + Breaker Block",
    tagline: "Temukan 'lubang' ketidakseimbangan harga yang menjadi magnet institusi",
    color: "#6366f1",
    what: "FVG (Fair Value Gap) adalah ketidakseimbangan antara pembeli dan penjual — 'lubang' 3 candle yang terbentuk saat harga bergerak terlalu cepat. Breaker Block adalah OB yang sudah ditembus dengan impulsif sehingga berbalik peran menjadi support/resistance kuat.",
    why: "FVG adalah magnet harga paling reliable di ICT methodology. Saat harga kembali ke titik tengah FVG (CE 50% Level), institusi sering menggunakannya sebagai pijakan kelanjutan tren.",
    how: [
      "Buka tab FVG+Breaker",
      "Periksa Auto Trade Plan di bagian atas (otomatis memilih FVG atau Breaker yang searah bias)",
      "Lihat FVG Cards dan CE Level (50% midpoint) untuk titik limit order paling presisi",
    ],
    steps: [
      { step: "Cara membaca FVG Card", detail: "Setiap card menampilkan: Gap Low/High (zone FVG), CE Level (50% = entry terbaik), ATR Multiplier (lebih besar = lebih kuat), Status (Fresh/Partial = terbaik), Strength 0–100." },
      { step: "CE Level = Entry Terbaik", detail: "CE (Consequent Encroachment) adalah titik tengah dari FVG. Saat price mencapai CE, ini adalah titik masuk paling presisi. Stop loss di bawah gap low (untuk Bullish FVG)." },
      { step: "ICT Setup Score", detail: "Lihat GradeRing di pojok kanan. A+ = semua konfluens ada, masuk dengan confidence. WAIT = terlalu sedikit konfluens, tunggu dulu." },
      { step: "Breaker Block = Bekas OB yang Berbalik Fungsi", detail: "Saat Bullish OB ditembus ke bawah, ia berubah menjadi Bearish Breaker (resistance). Saat Bearish OB ditembus ke atas, ia berubah menjadi Bullish Breaker (support)." },
    ],
    rules: [
      "✅ FVG FRESH = belum pernah disentuh = entry terbaik",
      "✅ Institutional FVG (>1.5x ATR) = magnet paling kuat",
      "✅ Pastikan arah FVG/Breaker searah dengan bias utama (Bullish untuk BUY, Bearish untuk SELL)",
      "❌ FVG yang sudah FILLED 100% atau Breaker yang sudah ditembus balik = tidak berlaku lagi",
    ],
    example: "BTC punya Bullish FVG di $63,000–$63,800 (CE = $63,400). Status FRESH. Strength 82. Price saat ini $65,500. Dalam NY Open Killzone, price turun ke $63,450 (tepat di CE). Setup IDEAL: BUY di $63,400, SL di $62,900, TP1 di $65,500, TP2 di $67,000. R:R = 1:3.",
    dontDo: ["Entry FVG saat sudah FILLED", "Memakai Bearish Breaker untuk sinyal BUY (harus searah)", "Miss Stacked FVGs — itu zone terkuat"],
  },
  {
    id: "position",
    category: "ICT & Smart Money Tools",
    icon: "⚖️",
    name: "Position Sizing Calculator",
    tagline: "Berapa ukuran posisi & leverage yang aman agar akun anti-MC?",
    color: "#a78bfa",
    what: "Position Sizing Calculator menghitung berapa besar kontrak ($ dan jumlah koin) yang optimal berdasarkan modal akun, persentase risiko per trade, serta jarak antara Entry dan Stop Loss. Dilengkapi Quarter Kelly Criterion & Risk of Ruin.",
    why: "Lebih dari 70% trader yang analisisnya benar tetap kehilangan akun mereka karena ukuran posisi (lot/leverage) terlalu besar saat mengalami 2–3 kali loss berturut-turut. Kalkulator ini menjaga agar setiap loss tidak pernah melebihi 1% modal Anda.",
    how: [
      "Klik tombol 🔢 Pos Calc langsung dari kartu Live Scanner atau ICT Confluence (Entry, SL, dan TP otomatis terisi), ATAU buka tab Position secara manual.",
      "Masukkan Account Size ($) dan Risk % yang diinginkan (disarankan 0.5%–1.5%).",
      "Gunakan angka Position Size yang dihasilkan saat membuka order di exchange.",
    ],
    steps: [
      { step: "Masukkan Account Size", detail: "Total modal trading kamu dalam USD. Contoh: $1,000 atau $10,000." },
      { step: "Set Risk Per Trade", detail: "Rekomendasi: 1% per trade. Dengan 1% risk, kamu perlu 100 trade loss berturut-turut untuk bangkrut — hampir mustahil jika mengikuti setup A+." },
      { step: "Verifikasi Entry & Stop Loss", detail: "Sistem menghitung otomatis: Position Size = (Account × Risk%) / |Entry - SL|." },
      { step: "Baca Quarter Kelly Criterion", detail: "Quarter Kelly (25% dari full Kelly) adalah batas atas risiko paling aman yang dipakai oleh manajer hedge fund profesional." },
    ],
    rules: [
      "✅ Maksimal risiko 0.5%–1.5% per trade untuk ketahanan jangka panjang",
      "✅ Gunakan Quarter Kelly sebagai batas atas ukuran posisi",
      "✅ Jika R:R kurang dari 1:1.5, lewati trade tersebut",
      "❌ Jangan pernah mempertaruhkan lebih dari 3–5% modal dalam satu transaksi",
      "❌ Jangan tambah posisi saat floating loss (averaging down tanpa rencana)",
    ],
    example: "Akun $10,000. Risk 1% = $100 risiko maksimal. Entry BUY di $63,400. SL di $62,900 (jarak SL $500). Position Size = $100 / $500 = 0.2 BTC. Jika kena SL, Anda hanya rugi tepat $100 (1%). Jika kena TP di $65,500, Anda profit $420 (+4.2R).",
    dontDo: ["Masuk posisi tanpa menghitung position size terlebih dahulu", "Menaikkan risk % secara emosional untuk 'balas dendam' setelah loss"],
  },
];

const CATEGORIES: Tool["category"][] = [
  "SOP & Pedoman Utama",
  "AI & Scanner Command",
  "ICT & Smart Money Tools",
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
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize:"0.76rem", fontWeight:800, color: active ? tool.color : "var(--text-secondary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{tool.name}</div>
        <div style={{ fontSize:"0.6rem", color:"var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{tool.tagline}</div>
      </div>
    </button>
  );
}

/* ── Main Page ── */
export default function GuideProPage() {
  const [activeTool, setActiveTool] = useState<ToolId>("sop-timeframe");
  const tool = TOOLS.find(t => t.id === activeTool)!;

  return (
    <MainLayout>
      {/* Header */}
      <div style={{ marginBottom:24 }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", gap:14, flexWrap:"wrap", marginBottom:8 }}>
          <div style={{ display:"flex", alignItems:"center", gap:14 }}>
            <div style={{ width:44, height:44, borderRadius:12, background:"linear-gradient(135deg,#6366f1,#a78bfa)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:"1.3rem", boxShadow:"0 0 20px rgba(99,102,241,0.3)", border:"1px solid rgba(255,255,255,0.1)" }}>
              📚
            </div>
            <div>
              <h1 style={{ fontFamily:"'Outfit',sans-serif", fontSize:"1.75rem", fontWeight:900, letterSpacing:"-0.04em", margin:0, background:"linear-gradient(135deg,#fff 30%,#94a3b8)", WebkitBackgroundClip:"text", WebkitTextFillColor:"transparent" }}>
                Pedoman &amp; Panduan Trading Sistem
              </h1>
              <p style={{ color:"var(--text-muted)", fontSize:"0.78rem", margin:0, marginTop:4 }}>
                SOP Timeframe (1H + 15M) · Alur Kerja 4 Langkah Pro Tools · DeepSeek-R1 AI Copilot · ICT Methodology
              </p>
            </div>
          </div>

          <div style={{ display:"flex", gap:10 }}>
            <Link href="/pro-tools" style={{ padding:"8px 14px", borderRadius:10, background:"rgba(232,121,249,0.12)", border:"1px solid rgba(232,121,249,0.35)", color:"#e879f9", fontSize:"0.72rem", fontWeight:800, textDecoration:"none" }}>
              ⚡ Buka Pro Tools
            </Link>
            <Link href="/charts" style={{ padding:"8px 14px", borderRadius:10, background:"rgba(56,189,248,0.12)", border:"1px solid rgba(56,189,248,0.35)", color:"#38bdf8", fontSize:"0.72rem", fontWeight:800, textDecoration:"none" }}>
              📈 Buka Charts + AI
            </Link>
          </div>
        </div>

        {/* ── Quick Reference Banner: Timeframe Matrix ── */}
        <div style={{
          marginTop: 14, padding: "14px 18px", borderRadius: 14,
          background: "linear-gradient(135deg, rgba(245,158,11,0.08), rgba(99,102,241,0.06))",
          border: "1px solid rgba(245,158,11,0.25)",
          display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12
        }}>
          <div style={{ padding: "8px 12px", borderRadius: 10, background: "rgba(0,0,0,0.25)", border: "1px solid rgba(245,158,11,0.3)" }}>
            <div style={{ fontSize: "0.6rem", fontWeight: 900, color: "#fbbf24", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              🏆 Standar Utama (Intraday)
            </div>
            <div style={{ fontSize: "0.82rem", fontWeight: 900, color: "#fff", marginTop: 3 }}>
              Scanner &amp; ICT: <span style={{ color: "#fbbf24" }}>1H</span> · Entry Chart: <span style={{ color: "#38bdf8" }}>15M</span>
            </div>
            <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", marginTop: 2 }}>
              HTF otomatis 4H. Bebas noise, SL ideal (0.8%–2.2%), target 4–24 jam.
            </div>
          </div>
          <div style={{ padding: "8px 12px", borderRadius: 10, background: "rgba(0,0,0,0.25)", border: "1px solid rgba(16,185,129,0.25)" }}>
            <div style={{ fontSize: "0.6rem", fontWeight: 900, color: "#34d399", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              ⚡ Active Session (Killzone)
            </div>
            <div style={{ fontSize: "0.82rem", fontWeight: 900, color: "#fff", marginTop: 3 }}>
              Scanner &amp; ICT: <span style={{ color: "#34d399" }}>15M</span> · Entry Chart: <span style={{ color: "#38bdf8" }}>15M / 5M</span>
            </div>
            <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", marginTop: 2 }}>
              Khusus London Open (14–17 WIB) &amp; NY Open (19–22 WIB). Wajib disiplin SL.
            </div>
          </div>
          <div style={{ padding: "8px 12px", borderRadius: 10, background: "rgba(0,0,0,0.25)", border: "1px solid rgba(167,139,250,0.25)" }}>
            <div style={{ fontSize: "0.6rem", fontWeight: 900, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              🌊 Swing Trader (Sibuk Kerja)
            </div>
            <div style={{ fontSize: "0.82rem", fontWeight: 900, color: "#fff", marginTop: 3 }}>
              Scanner &amp; ICT: <span style={{ color: "#a78bfa" }}>4H</span> · Entry Chart: <span style={{ color: "#38bdf8" }}>1H</span>
            </div>
            <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", marginTop: 2 }}>
              HTF otomatis 1D. Cukup cek pagi &amp; malam, tahan posisi 2–7 hari.
            </div>
          </div>
        </div>
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"295px 1fr", gap:24, alignItems:"start" }}>

        {/* ── Sidebar: categorized tool list ── */}
        <div style={{ display:"flex", flexDirection:"column", gap:12, position:"sticky", top:20 }}>
          {CATEGORIES.map(cat => (
            <div key={cat} style={{ display:"flex", flexDirection:"column", gap:5 }}>
              <div style={{ fontSize:"0.58rem", fontWeight:800, color:"var(--text-muted)", textTransform:"uppercase", letterSpacing:"0.1em", paddingLeft:4 }}>
                {cat}
              </div>
              {TOOLS.filter(t => t.category === cat).map(t => (
                <ToolGuide key={t.id} tool={t} active={activeTool === t.id} onSelect={() => setActiveTool(t.id)} />
              ))}
            </div>
          ))}

          {/* Quick links */}
          <div style={{ marginTop:6, padding:"14px 16px", borderRadius:12, background:"rgba(99,102,241,0.06)", border:"1px solid rgba(99,102,241,0.15)" }}>
            <div style={{ fontSize:"0.7rem", fontWeight:800, color:"#6366f1", marginBottom:8 }}>📋 Checklist Wajib Sebelum Entry</div>
            {[
              "✅ Scanner / ICT Grade A+ atau VALID",
              "✅ Analisis di 1H, konfirmasi entry di 15M",
              "✅ BUY di Discount (<38%) / SELL di Premium (>62%)",
              "✅ Searah HTF (4H/1D) atau ada Liquidity Sweep",
              "✅ R:R minimal 1:2 & sudah cek DeepSeek AI",
              "✅ Hitung lot di Pos Calc (Risk maks 1%)",
            ].map((item, i) => (
              <div key={i} style={{ fontSize:"0.64rem", color:"var(--text-muted)", marginBottom:4, lineHeight:1.45 }}>{item}</div>
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
                <div style={{ fontSize:"0.6rem", fontWeight:800, color:tool.color, textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:3 }}>
                  {tool.category}
                </div>
                <h2 style={{ margin:0, fontSize:"1.3rem", fontWeight:900, color:"#fff" }}>{tool.name}</h2>
                <div style={{ fontSize:"0.85rem", color:tool.color, fontWeight:700, marginTop:4 }}>{tool.tagline}</div>
              </div>
            </div>
          </div>

          {/* WHAT */}
          <div style={{ padding:"18px 20px", borderRadius:14, background:"rgba(255,255,255,0.02)", border:"1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ fontSize:"0.65rem", fontWeight:800, color:`${tool.color}`, textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:8 }}>Apa itu &amp; Fokus Utamanya</div>
            <p style={{ fontSize:"0.85rem", color:"var(--text-secondary)", lineHeight:1.8, margin:0 }}>{tool.what}</p>
          </div>

          {/* WHY */}
          <div style={{ padding:"18px 20px", borderRadius:14, background:`${tool.color}06`, border:`1px solid ${tool.color}18` }}>
            <div style={{ fontSize:"0.65rem", fontWeight:800, color:tool.color, textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:8 }}>Mengapa Penting?</div>
            <p style={{ fontSize:"0.85rem", color:"var(--text-secondary)", lineHeight:1.8, margin:0 }}>💡 {tool.why}</p>
          </div>

          {/* HOW TO USE */}
          <div style={{ padding:"18px 20px", borderRadius:14, background:"rgba(255,255,255,0.02)", border:"1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ fontSize:"0.65rem", fontWeight:800, color:tool.color, textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:14 }}>Pedoman Praktis</div>
            <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
              {tool.how.map((h, i) => (
                <div key={i} style={{ display:"flex", alignItems:"flex-start", gap:10 }}>
                  <div style={{ width:22, height:22, borderRadius:6, flexShrink:0, background:`${tool.color}20`, border:`1px solid ${tool.color}40`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:"0.65rem", fontWeight:900, color:tool.color }}>{i+1}</div>
                  <div style={{ fontSize:"0.78rem", color:"var(--text-secondary)", paddingTop:2, lineHeight:1.55 }}>{h}</div>
                </div>
              ))}
            </div>
          </div>

          {/* STEPS */}
          <div style={{ padding:"18px 20px", borderRadius:14, background:"rgba(255,255,255,0.02)", border:"1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ fontSize:"0.65rem", fontWeight:800, color:tool.color, textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:14 }}>Step-by-step Workflow</div>
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
              <div style={{ fontSize:"0.65rem", fontWeight:800, color:"#10b981", textTransform:"uppercase", marginBottom:10 }}>Rules — Wajib Lakukan</div>
              {tool.rules.filter(r => r.startsWith("✅")).map((r, i) => (
                <div key={i} style={{ fontSize:"0.72rem", color:"var(--text-muted)", marginBottom:6, lineHeight:1.5 }}>{r}</div>
              ))}
            </div>
            <div style={{ padding:"16px 18px", borderRadius:14, background:"rgba(239,68,68,0.05)", border:"1px solid rgba(239,68,68,0.15)" }}>
              <div style={{ fontSize:"0.65rem", fontWeight:800, color:"#ef4444", textTransform:"uppercase", marginBottom:10 }}>Pantangan — Hindari</div>
              {tool.rules.filter(r => r.startsWith("❌")).map((r, i) => (
                <div key={i} style={{ fontSize:"0.72rem", color:"var(--text-muted)", marginBottom:6, lineHeight:1.5 }}>{r}</div>
              ))}
            </div>
          </div>

          {/* REAL EXAMPLE */}
          <div style={{ padding:"18px 20px", borderRadius:14, background:"rgba(99,102,241,0.06)", border:"1px solid rgba(99,102,241,0.2)" }}>
            <div style={{ fontSize:"0.65rem", fontWeight:800, color:"#6366f1", textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:10 }}>Contoh Penerapan Nyata</div>
            <div style={{ fontSize:"0.78rem", color:"var(--text-secondary)", lineHeight:1.8 }}>
              {tool.example}
            </div>
          </div>

          {/* DONT DO */}
          <div style={{ padding:"16px 18px", borderRadius:14, background:"rgba(245,158,11,0.05)", border:"1px solid rgba(245,158,11,0.2)" }}>
            <div style={{ fontSize:"0.65rem", fontWeight:800, color:"#f59e0b", textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:10 }}>Kesalahan Umum — Jangan Diulangi!</div>
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
