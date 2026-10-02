"""
ICT Alert Engine
================
Generates WhatsApp notifications ONLY for high-quality ICT setups.

Alert Types:
  1. KILLZONE_START  — session begins (remind trader to watch)
  2. FVG_HIT         — price enters a fresh FVG CE level  
  3. SWEEP_CONFIRMED — sweep + displacement confirmed (highest probability)
  4. COMPOSITE_SCORE — ICT composite score exceeds threshold
  5. VOLUME_SPIKE    — abnormal volume surge detected
  6. DAILY_BRIEF     — morning session summary (London open)

Innovation Features:
  - Grade filter: only A/A+ setups get through (no spam)
  - Per-symbol cooldown: 4h between same alerts  
  - Killzone-aware: alerts respect active session windows
  - Full entry plan embedded in message (entry / SL / TP / RR)
  - Rich WhatsApp markdown formatting
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    KILLZONE_START  = "KILLZONE_START"
    FVG_HIT         = "FVG_HIT"
    SWEEP_CONFIRMED = "SWEEP_CONFIRMED"
    COMPOSITE_SCORE = "COMPOSITE_SCORE"
    VOLUME_SPIKE    = "VOLUME_SPIKE"
    DAILY_BRIEF     = "DAILY_BRIEF"
    TEST            = "TEST"


class AlertGrade(str, Enum):
    A_PLUS = "A+"
    A      = "A"
    B      = "B"
    C      = "C"


@dataclass
class AlertConfig:
    """User-configurable alert settings (persisted in DB/file)."""
    phone: str                            # WA number e.g. "628123456789"
    enabled: bool = True

    # Which alert types to receive
    killzone_start:   bool = True
    fvg_hit:          bool = True
    sweep_confirmed:  bool = True
    composite_score:  bool = True
    volume_spike:     bool = False
    daily_brief:      bool = True

    # Thresholds
    min_score:        int   = 70          # 0-100; only alert if score ≥ this
    min_grade:        str   = "A"         # A+, A, B, C
    symbols:          List[str] = field(default_factory=lambda: ["BTCUSDT","ETHUSDT","SOLUSDT"])
    only_killzone:    bool = True         # only alert during active sessions

    # Anti-spam
    cooldown_hours:   int  = 4            # hours between same alert type/symbol
    max_per_hour:     int  = 3            # max total alerts per hour


@dataclass
class TradeAlert:
    """A generated alert ready to be sent."""
    alert_type:   AlertType
    symbol:       str
    grade:        str
    score:        int
    title:        str
    message:      str
    entry:        Optional[float] = None
    sl:           Optional[float] = None
    tp1:          Optional[float] = None
    tp2:          Optional[float] = None
    rr:           Optional[float] = None
    timeframe:    str = "1h"
    session:      str = ""
    timestamp:    datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ICTAlertEngine:
    """
    Monitors trading conditions and generates WhatsApp alerts
    for high-quality ICT setups.
    """

    GRADE_MIN_SCORE = {"A+": 80, "A": 65, "B": 50, "C": 35}

    SESSION_INFO = {
        "ASIA":    ("🌏", "Asia",    (0,  7)),
        "LONDON":  ("🇬🇧", "London",  (7,  12)),
        "NY_OPEN": ("🗽", "NY Open", (12, 17)),
        "NY_PM":   ("🌆", "NY PM",   (17, 20)),
        "DEAD":    ("😴", "Dead Zone",(20, 24)),
    }

    def __init__(self):
        # Cooldown tracker: {(symbol, alert_type): last_sent_utc}
        self._cooldowns: Dict[tuple, datetime] = {}
        # Rate limiter: list of sent timestamps this hour
        self._sent_this_hour: List[datetime] = []

    # ─────────────────────────────────────────────────────────────────────────
    # Main entry points
    # ─────────────────────────────────────────────────────────────────────────

    def generate_alert(
        self,
        alert_type: AlertType,
        symbol: str,
        config: AlertConfig,
        data: dict,
    ) -> Optional[TradeAlert]:
        """
        Check conditions and generate a TradeAlert if criteria are met.
        Returns None if alert should be suppressed (cooldown, grade filter, etc).
        """
        if not config.enabled:
            return None

        # ── Grade / Score filter ───────────────────────────────────────────
        score = data.get("score", 0)
        grade = data.get("grade", "C")
        if score < config.min_score:
            logger.debug(f"Alert suppressed: score {score} < {config.min_score}")
            return None
        if not self._grade_passes(grade, config.min_grade):
            logger.debug(f"Alert suppressed: grade {grade} < {config.min_grade}")
            return None

        # ── Session filter ─────────────────────────────────────────────────
        session = self._current_session()
        if config.only_killzone and session not in ("LONDON", "NY_OPEN"):
            logger.debug(f"Alert suppressed: not in killzone (session={session})")
            return None

        # ── Symbol filter ──────────────────────────────────────────────────
        if config.symbols and symbol not in config.symbols:
            return None

        # ── Type filter ────────────────────────────────────────────────────
        type_enabled = {
            AlertType.KILLZONE_START:  config.killzone_start,
            AlertType.FVG_HIT:         config.fvg_hit,
            AlertType.SWEEP_CONFIRMED: config.sweep_confirmed,
            AlertType.COMPOSITE_SCORE: config.composite_score,
            AlertType.VOLUME_SPIKE:    config.volume_spike,
            AlertType.DAILY_BRIEF:     config.daily_brief,
        }
        if not type_enabled.get(alert_type, True):
            return None

        # ── Cooldown ───────────────────────────────────────────────────────
        key = (symbol, alert_type)
        if key in self._cooldowns:
            elapsed = datetime.now(timezone.utc) - self._cooldowns[key]
            if elapsed < timedelta(hours=config.cooldown_hours):
                remaining = int((timedelta(hours=config.cooldown_hours) - elapsed).total_seconds() / 60)
                logger.debug(f"Alert on cooldown: {remaining}m remaining for {symbol}/{alert_type}")
                return None

        # ── Rate limit ─────────────────────────────────────────────────────
        now = datetime.now(timezone.utc)
        self._sent_this_hour = [t for t in self._sent_this_hour if (now - t) < timedelta(hours=1)]
        if len(self._sent_this_hour) >= config.max_per_hour:
            logger.debug(f"Rate limit reached: {len(self._sent_this_hour)}/{config.max_per_hour} alerts this hour")
            return None

        # ── Build alert ────────────────────────────────────────────────────
        alert = self._build_alert(alert_type, symbol, grade, score, session, data)
        if alert:
            self._cooldowns[key] = now
            self._sent_this_hour.append(now)
        return alert

    def _build_alert(
        self, alert_type: AlertType, symbol: str,
        grade: str, score: int, session: str, data: dict
    ) -> TradeAlert:

        emoji, sess_name, _ = self.SESSION_INFO.get(session, ("📊", session, (0, 24)))
        entry = data.get("entry")
        sl    = data.get("sl")
        tp1   = data.get("tp1")
        tp2   = data.get("tp2")
        rr    = data.get("rr")
        price = data.get("price", 0)
        tf    = data.get("timeframe", "1h")

        builders = {
            AlertType.COMPOSITE_SCORE: self._build_composite,
            AlertType.FVG_HIT:         self._build_fvg_hit,
            AlertType.SWEEP_CONFIRMED: self._build_sweep,
            AlertType.KILLZONE_START:  self._build_killzone_start,
            AlertType.VOLUME_SPIKE:    self._build_volume_spike,
            AlertType.DAILY_BRIEF:     self._build_daily_brief,
            AlertType.TEST:            self._build_test,
        }
        builder = builders.get(alert_type, self._build_composite)
        return builder(symbol, grade, score, session, sess_name, emoji, tf, data)

    # ─────────────────────────────────────────────────────────────────────────
    # Message builders — each produces rich WA-markdown formatted text
    # ─────────────────────────────────────────────────────────────────────────

    def _build_composite(self, sym, grade, score, session, sess_name, emoji, tf, d) -> TradeAlert:
        bias = d.get("entry_bias", "NEUTRAL")
        bias_icon = "🟢" if "BUY" in bias else "🔴" if "SELL" in bias else "⚪"

        checks = []
        if d.get("in_discount"):    checks.append("✅ Discount/Premium Zone")
        if d.get("fvg_fresh"):      checks.append(f"✅ Fresh FVG ({d.get('fvg_high','?')} – {d.get('fvg_low','?')})")
        if d.get("ce_level"):       checks.append(f"✅ CE Level: {d.get('ce_level','?')}")
        if d.get("sweep_confirmed"):checks.append("✅ Liquidity Sweep confirmed")
        if d.get("ob_active"):      checks.append("✅ Order Block ACTIVE")
        if d.get("breaker_active"): checks.append("✅ Breaker Block ACTIVE")
        if not checks:              checks.append("📊 Multiple ICT factors aligned")

        entry_plan = self._format_entry(d)
        grade_bar  = self._grade_bar(score)

        msg = (
            f"🎯 *ICT SETUP ALERT — {grade} GRADE*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *{sym}* · {tf.upper()} · {emoji} {sess_name}\n"
            f"⚡ Score: *{score}/100* {grade_bar}\n"
            f"\n"
            f"{bias_icon} *Bias: {bias}*\n"
            f"\n"
            f"*Kondisi ICT:*\n"
            + "\n".join(f"  {c}" for c in checks) +
            f"\n\n{entry_plan}"
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"_TradingSistem · ICT Methodology_"
        )
        return TradeAlert(
            alert_type=AlertType.COMPOSITE_SCORE, symbol=sym,
            grade=grade, score=score, title=f"A+ Setup: {sym}",
            message=msg, session=session, timeframe=tf,
            entry=d.get("entry"), sl=d.get("sl"),
            tp1=d.get("tp1"), tp2=d.get("tp2"), rr=d.get("rr"),
        )

    def _build_fvg_hit(self, sym, grade, score, session, sess_name, emoji, tf, d) -> TradeAlert:
        fvg_type = d.get("fvg_type", "Bullish")
        ce       = d.get("ce_level", "?")
        gap_high = d.get("fvg_high", "?")
        gap_low  = d.get("fvg_low",  "?")
        fill_pct = d.get("fill_pct", 0)
        entry_plan = self._format_entry(d)

        type_icon = "🟢" if fvg_type == "Bullish" else "🔴"

        msg = (
            f"⬜ *FVG ALERT — Price Masuk Gap*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *{sym}* · {tf.upper()} · {emoji} {sess_name}\n"
            f"\n"
            f"{type_icon} *{fvg_type} FVG* (FRESH)\n"
            f"  Gap: {gap_low} – {gap_high}\n"
            f"  📍 CE Level: *{ce}* ← entry presisi\n"
            f"  Fill: {fill_pct:.0f}%\n"
            f"\n"
            f"{entry_plan}"
            f"\n💡 _FVG = imbalance institusional. CE = 50% gap = titik entry ICT_\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"_TradingSistem · ICT Methodology_"
        )
        return TradeAlert(
            alert_type=AlertType.FVG_HIT, symbol=sym, grade=grade,
            score=score, title=f"FVG Hit: {sym}", message=msg, session=session,
        )

    def _build_sweep(self, sym, grade, score, session, sess_name, emoji, tf, d) -> TradeAlert:
        sweep_type  = d.get("sweep_type", "Equal Lows")
        displace    = d.get("displacement", False)
        level       = d.get("swept_level", "?")
        entry_plan  = self._format_entry(d)
        displace_txt = "✅ *Displacement confirmed!*" if displace else "⏳ Menunggu displacement..."

        msg = (
            f"🌊 *LIQUIDITY SWEEP ALERT*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *{sym}* · {tf.upper()} · {emoji} {sess_name}\n"
            f"\n"
            f"🎯 Sweep: *{sweep_type}*\n"
            f"  Level: {level}\n"
            f"  {displace_txt}\n"
            f"\n"
            f"{entry_plan}"
            f"\n💡 _Smart Money sedang mengambil likuiditas. Tunggu displacement sebelum entry._\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"_TradingSistem · ICT Methodology_"
        )
        return TradeAlert(
            alert_type=AlertType.SWEEP_CONFIRMED, symbol=sym, grade=grade,
            score=score, title=f"Sweep: {sym}", message=msg, session=session,
        )

    def _build_killzone_start(self, sym, grade, score, session, sess_name, emoji, tf, d) -> TradeAlert:
        watch  = d.get("watch_levels", [])
        pairs  = d.get("top_pairs", ["BTCUSDT", "ETHUSDT", "SOLUSDT"])[:5]
        watch_str = "\n".join(f"  • {w}" for w in watch[:4]) if watch else "  • Lihat chart untuk level kunci"
        pairs_str = " | ".join(p.replace("USDT","") for p in pairs)

        msg = (
            f"{emoji} *{sess_name.upper()} KILLZONE DIMULAI*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {datetime.now(timezone.utc).strftime('%H:%M')} UTC\n"
            f"\n"
            f"📊 *Top Pairs Sesi Ini:*\n"
            f"  {pairs_str}\n"
            f"\n"
            f"⚠️ *Levels to Watch:*\n"
            f"{watch_str}\n"
            f"\n"
            f"📋 *Checklist:*\n"
            f"  ☐ Cek PD Zone (premium/discount?)\n"
            f"  ☐ Tandai Equal High/Low (likuiditas)\n"
            f"  ☐ Identifikasi FVG & OB terdekat\n"
            f"  ☐ Tunggu sweep sebelum entry\n"
            f"\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"_TradingSistem · ICT Methodology_"
        )
        return TradeAlert(
            alert_type=AlertType.KILLZONE_START, symbol="ALL", grade="INFO",
            score=0, title=f"{sess_name} Killzone", message=msg, session=session,
        )

    def _build_volume_spike(self, sym, grade, score, session, sess_name, emoji, tf, d) -> TradeAlert:
        vol_mult = d.get("volume_multiplier", 2.0)
        direction = d.get("direction", "UP")
        dir_icon  = "📈" if direction == "UP" else "📉"
        price     = d.get("price", 0)

        msg = (
            f"📊 *VOLUME SPIKE ALERT*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *{sym}* · {tf.upper()} · {emoji} {sess_name}\n"
            f"\n"
            f"{dir_icon} Volume: *{vol_mult:.1f}x* rata-rata normal\n"
            f"  Harga: {price}\n"
            f"  Arah: {direction}\n"
            f"\n"
            f"💡 _Volume spike besar biasanya menandai gerakan institusional. Perhatikan displacement candle berikutnya._\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"_TradingSistem · ICT Methodology_"
        )
        return TradeAlert(
            alert_type=AlertType.VOLUME_SPIKE, symbol=sym, grade=grade,
            score=score, title=f"Volume Spike: {sym}", message=msg, session=session,
        )

    def _build_daily_brief(self, sym, grade, score, session, sess_name, emoji, tf, d) -> TradeAlert:
        pairs = d.get("pairs_summary", [])
        lines = []
        for p in pairs[:5]:
            ch = p.get("change_24h", 0)
            icon = "🟢" if ch >= 0 else "🔴"
            lines.append(f"  {icon} *{p['symbol'].replace('USDT','')}*: {p.get('price','?')} ({'+' if ch>=0 else ''}{ch:.2f}%)")

        msg = (
            f"🌅 *DAILY BRIEF — {sess_name}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 {datetime.now(timezone.utc).strftime('%a %d %b %Y')} · {datetime.now(timezone.utc).strftime('%H:%M')} UTC\n"
            f"\n"
            f"📊 *Market Overview:*\n"
            + "\n".join(lines) +
            f"\n\n"
            f"🎯 *Focus hari ini:*\n"
            f"  • {d.get('focus', 'Monitor London & NY Open killzones')}\n"
            f"\n"
            f"⚡ *Setup terbaik:* {d.get('best_setup', 'Belum ada konfirmasi')}\n"
            f"\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"_TradingSistem · Good luck, trade safe!_ 🙏"
        )
        return TradeAlert(
            alert_type=AlertType.DAILY_BRIEF, symbol="ALL", grade="INFO",
            score=0, title="Daily Brief", message=msg, session=session,
        )

    def _build_test(self, sym, grade, score, session, sess_name, emoji, tf, d) -> TradeAlert:
        msg = (
            f"✅ *TEST ALERT — TradingSistem WA Aktif!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎉 Koneksi WhatsApp berhasil!\n\n"
            f"📱 *Notifikasi yang akan kamu terima:*\n"
            f"  • 🎯 ICT Setup A/A+ grade\n"
            f"  • ⬜ FVG hit alert (CE level)\n"
            f"  • 🌊 Liquidity sweep confirmed\n"
            f"  • 🗽 Killzone start reminder\n"
            f"  • 🌅 Daily brief (London open)\n\n"
            f"⚙️ *Konfigurasi saat ini:*\n"
            f"  Min score: {d.get('min_score', 70)}/100\n"
            f"  Min grade: {d.get('min_grade', 'A')}\n"
            f"  Cooldown: {d.get('cooldown_hours', 4)}h\n"
            f"  Max/jam: {d.get('max_per_hour', 3)}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"_TradingSistem · ICT Methodology_"
        )
        return TradeAlert(
            alert_type=AlertType.TEST, symbol="TEST", grade="INFO",
            score=100, title="Test Alert", message=msg, session=session,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _format_entry(self, d: dict) -> str:
        entry = d.get("entry")
        sl    = d.get("sl")
        tp1   = d.get("tp1")
        tp2   = d.get("tp2")
        rr    = d.get("rr")

        if not entry:
            return ""

        def fmtp(v):
            if v is None: return "—"
            if v >= 1000: return f"{v:,.2f}"
            return f"{v:.4f}"

        sl_pct = abs((sl - entry) / entry * 100) if sl and entry else 0
        tp1_pct = abs((tp1 - entry) / entry * 100) if tp1 and entry else 0

        lines = [
            "💰 *Entry Plan:*",
            f"  🟡 Entry:  {fmtp(entry)}",
            f"  🔴 SL:     {fmtp(sl)} (-{sl_pct:.2f}%)",
            f"  🟢 TP1:    {fmtp(tp1)} (+{tp1_pct:.2f}%)",
        ]
        if tp2:
            tp2_pct = abs((tp2 - entry) / entry * 100) if entry else 0
            lines.append(f"  🟢 TP2:    {fmtp(tp2)} (+{tp2_pct:.2f}%)")
        if rr:
            lines.append(f"  ⚖️ R:R:    1:{rr:.1f}")

        lines.append(f"  ⚠️ _Max risk: 1% akun_\n")
        return "\n".join(lines)

    @staticmethod
    def _grade_bar(score: int) -> str:
        filled = int(score / 10)
        return "▓" * filled + "░" * (10 - filled)

    @staticmethod
    def _grade_passes(grade: str, min_grade: str) -> bool:
        order = {"A+": 4, "A": 3, "B": 2, "C": 1}
        return order.get(grade, 0) >= order.get(min_grade, 3)

    @staticmethod
    def _current_session() -> str:
        h = datetime.now(timezone.utc).hour
        if  0 <= h <  7: return "ASIA"
        if  7 <= h < 12: return "LONDON"
        if 12 <= h < 17: return "NY_OPEN"
        if 17 <= h < 20: return "NY_PM"
        return "DEAD"
