"""
Bandar / Institutional Flow Anomaly Notifier & Background Daemon.

Monitors IDX intraday tick / broker summary / stock summary volume spikes,
flags sudden institutional absorption (foreign buy concentration vs retail distribution),
and dispatches private Telegram alerts when an anomaly threshold crosses 3σ (Z >= 3.0).

Statistical Foundations:
- Rolling lookback window (default 20 sessions) to establish baseline:
    mu_vol, sigma_vol = mean and std of volume
    mu_val, sigma_val = mean and std of turnover value
    mu_nff, sigma_nff = mean and std of net foreign flow
- Z-score calculations:
    Z_vol = (Volume - mu_vol) / max(sigma_vol, 1.0)
    Z_val = (Value - mu_val) / max(sigma_val, 1.0)
    Z_nff = (NetForeignFlow - mu_nff) / max(sigma_nff, 1.0)
- Anomaly Threshold: Z >= 3.0 (crossing 3 standard deviations, 99.87th percentile anomaly)
- Patterns Detected:
    1. INSTITUTIONAL_ABSORPTION: Z >= 3.0, heavy Foreign/Smart Buy, flat price (|dP| <= 1.5%)
    2. INSTITUTIONAL_MARKUP: Z >= 3.0, heavy Foreign/Smart Buy, bullish breakout (dP > +2.0%)
    3. RETAIL_TRAP_DISTRIBUTION: Z >= 3.0, retail buy concentration into smart money selling
    4. INSTITUTIONAL_DUMP: Z_nff <= -3.0, massive foreign/smart liquidation
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any

import pandas as pd

from idx.core.utils import DATA_DIR, get_logger, load_json

log = get_logger("idx.bandar_notifier")

PARQUET_DIR = os.path.join(DATA_DIR, "parquet")
ALERTS_FILE = os.path.join(DATA_DIR, "anomaly_alerts.json")

# Smart money vs Retail brokers
SMART_BROKERS = frozenset({"AK", "BK", "ZP", "CS", "KZ", "RX", "CC", "LG", "DX", "AI", "MS", "CG"})
RETAIL_BROKERS = frozenset({"YP", "PD", "XC", "NI", "KK", "CP", "AZ", "OD", "SQ", "XL"})


class BandarAnomalyAlert:
    """Represents a validated statistical anomaly event."""

    def __init__(
        self,
        ticker: str,
        company_name: str,
        date: str,
        price: float,
        price_change_pct: float,
        volume: float,
        turnover_rp: float,
        net_foreign_flow_rp: float,
        foreign_buy_ratio_pct: float,
        z_vol: float,
        z_val: float,
        z_nff: float,
        z_composite: float,
        anomaly_type: str,
        wyckoff_phase: str,
        smart_money_delta: float,
        headline: str,
        playbook: str,
        timestamp: str | None = None,
    ):
        self.ticker = ticker.upper()
        self.company_name = company_name
        self.date = date
        self.price = price
        self.price_change_pct = price_change_pct
        self.volume = volume
        self.turnover_rp = turnover_rp
        self.net_foreign_flow_rp = net_foreign_flow_rp
        self.foreign_buy_ratio_pct = foreign_buy_ratio_pct
        self.z_vol = z_vol
        self.z_val = z_val
        self.z_nff = z_nff
        self.z_composite = z_composite
        self.anomaly_type = anomaly_type
        self.wyckoff_phase = wyckoff_phase
        self.smart_money_delta = smart_money_delta
        self.headline = headline
        self.playbook = playbook
        self.timestamp = timestamp or datetime.datetime.now(datetime.UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "date": self.date,
            "timestamp": self.timestamp,
            "price": round(self.price, 2),
            "price_change_pct": round(self.price_change_pct, 2),
            "volume": round(self.volume, 0),
            "turnover_rp": round(self.turnover_rp, 2),
            "turnover_rp_b": round(self.turnover_rp / 1e9, 2),
            "net_foreign_flow_rp": round(self.net_foreign_flow_rp, 2),
            "net_foreign_flow_rp_b": round(self.net_foreign_flow_rp / 1e9, 2),
            "foreign_buy_ratio_pct": round(self.foreign_buy_ratio_pct, 1),
            "z_vol": round(self.z_vol, 2),
            "z_val": round(self.z_val, 2),
            "z_nff": round(self.z_nff, 2),
            "z_composite": round(self.z_composite, 2),
            "anomaly_type": self.anomaly_type,
            "wyckoff_phase": self.wyckoff_phase,
            "smart_money_delta": round(self.smart_money_delta, 2),
            "headline": self.headline,
            "playbook": self.playbook,
        }

    def format_telegram_message(self) -> str:
        """Formats the alert as a high-visibility Telegram Markdown message."""
        sign = "+" if self.price_change_pct >= 0 else ""
        nff_sign = "+" if self.net_foreign_flow_rp >= 0 else ""

        if self.anomaly_type == "INSTITUTIONAL_ABSORPTION":
            badge = "🐋 *INSTITUTIONAL ABSORPTION (AKUMULASI SENYAP)*"
            icon = "🚨"
        elif self.anomaly_type == "INSTITUTIONAL_MARKUP":
            badge = "🚀 *INSTITUTIONAL MARKUP (HAJAR KANAN)*"
            icon = "🔥"
        elif self.anomaly_type == "RETAIL_TRAP_DISTRIBUTION":
            badge = "🪤 *RETAIL TRAP ALERT (JEBAKAN RITEL)*"
            icon = "⚠️"
        else:
            badge = "📉 *INSTITUTIONAL DISTRIBUTION (GUYURAN MASIF)*"
            icon = "🚨"

        msg = (
            f"{icon} *BANDAR ANOMALY NOTIFIER: {self.z_composite:.1f}σ SPIKE*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*Ticker:* `{self.ticker}` — {self.company_name}\n"
            f"*Pattern:* {badge}\n"
            f"*Severity:* `{self.z_composite:.2f}σ` statistical outlier\n"
            f"*Wyckoff:* _{self.wyckoff_phase}_\n\n"
            f"📊 *Volume & Flow Dynamics:*\n"
            f"• *Price:* Rp {self.price:,.0f} ({sign}{self.price_change_pct:.2f}%)\n"
            f"• *Turnover:* Rp {self.turnover_rp / 1e9:,.2f}B (Z-Vol: `{self.z_vol:+.2f}σ`)\n"
            f"• *Net Foreign Flow:* {nff_sign}Rp {self.net_foreign_flow_rp / 1e9:,.2f}B (Z-NFF: `{self.z_nff:+.2f}σ`)\n"
            f"• *Foreign Buy Ratio:* {self.foreign_buy_ratio_pct:.1f}% of total volume\n"
            f"• *Smart Money Delta:* {self.smart_money_delta:.1f}x retail volume\n\n"
            f"🎯 *Actionable Bandar Playbook:*\n"
            f"{self.playbook}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ _IDX-BEI Quantitative Telemetry • {self.timestamp[:19]}_"
        )
        return msg


def send_telegram_alert(
    message: str,
    bot_token: str | None = None,
    chat_id: str | None = None,
    timeout: int = 10,
) -> bool:
    """Dispatches a formatted Markdown alert to a private Telegram chat/channel.

    Reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from env if not passed explicitly.
    """
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat:
        log.info(
            "Telegram notification skipped (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured)"
        )
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "IDX-BEI-BandarNotifier/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                log.info("Telegram alert delivered successfully to chat_id=%s", chat)
                return True
            log.warning("Telegram API responded with HTTP %d", resp.status)
            return False
    except Exception as e:
        log.error("Failed to deliver Telegram alert: %s", e)
        return False


def test_telegram_connection(
    bot_token: str | None = None, chat_id: str | None = None
) -> dict[str, Any]:
    """Tests the Telegram Bot connection with a diagnostic verification message."""
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not token:
        return {"ok": False, "error": "Missing TELEGRAM_BOT_TOKEN in environment or args"}
    if not chat:
        return {"ok": False, "error": "Missing TELEGRAM_CHAT_ID in environment or args"}

    now_str = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    test_msg = (
        f"🤖 *IDX-BEI Bandar Notifier Connected*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✓ Telegram webhook telemetry operational.\n"
        f"✓ Listening for 3σ volume spikes and institutional flow anomalies.\n"
        f"⏱ _Timestamp: {now_str}_"
    )
    ok = send_telegram_alert(test_msg, bot_token=token, chat_id=chat)
    return {"ok": ok, "chat_id": chat, "timestamp": now_str}


def detect_bandar_anomalies(
    stock_df: pd.DataFrame | None = None,
    broker_df: pd.DataFrame | None = None,
    lookback_sessions: int = 20,
    sigma_threshold: float = 3.0,
    min_turnover_rp: float = 2_000_000_000.0,
    on_date: str | None = None,
) -> list[BandarAnomalyAlert]:
    """Scans market sessions to detect institutional absorption & volume anomalies crossing 3σ.

    Args:
        stock_df: stock_summary DataFrame (Date, StockCode, Close, Previous, Volume, Value, ForeignBuy, ForeignSell)
        broker_df: optional broker_summary DataFrame (Date, IDFirm, Value, Volume)
        lookback_sessions: baseline rolling window (default 20)
        sigma_threshold: anomaly cutoff Z-score (default 3.0)
        min_turnover_rp: minimum session turnover to filter penny illiquidity (default 2B IDR)
        on_date: target session ISO date string (default: latest date in data)

    Returns:
        List of BandarAnomalyAlert objects sorted by descending severity (z_composite).
    """
    if stock_df is None:
        stock_path = os.path.join(PARQUET_DIR, "stock_summary.parquet")
        if os.path.exists(stock_path):
            stock_df = pd.read_parquet(stock_path)
        else:
            return []

    if stock_df.empty or "StockCode" not in stock_df.columns:
        return []

    df = stock_df.copy()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date")
        if on_date:
            target_dt = pd.to_datetime(on_date)
            df = df[df["Date"] <= target_dt]

    all_dates = sorted(df["Date"].unique())
    if len(all_dates) < 2:
        return []

    latest_date = all_dates[-1]
    window_dates = (
        all_dates[-(lookback_sessions + 1) : -1]
        if len(all_dates) > lookback_sessions
        else all_dates[:-1]
    )

    latest_slice = df[df["Date"] == latest_date]
    baseline_slice = df[df["Date"].isin(window_dates)]

    # Compute baseline statistics per stock
    baseline_stats = {}
    if not baseline_slice.empty:
        for ticker, grp in baseline_slice.groupby("StockCode"):
            v_s = grp["Volume"].dropna().astype(float)
            val_s = grp["Value"].dropna().astype(float) if "Value" in grp.columns else v_s * 1000.0

            fb = (
                grp["ForeignBuy"].dropna().astype(float)
                if "ForeignBuy" in grp.columns
                else pd.Series(0.0)
            )
            fs = (
                grp["ForeignSell"].dropna().astype(float)
                if "ForeignSell" in grp.columns
                else pd.Series(0.0)
            )
            cl = grp["Close"].dropna().astype(float) if "Close" in grp.columns else pd.Series(0.0)
            nff_s = (fb - fs) * cl

            baseline_stats[ticker] = {
                "mean_vol": float(v_s.mean()) if len(v_s) > 0 else 0.0,
                "std_vol": float(v_s.std()) if len(v_s) > 1 else 0.0,
                "mean_val": float(val_s.mean()) if len(val_s) > 0 else 0.0,
                "std_val": float(val_s.std()) if len(val_s) > 1 else 0.0,
                "mean_nff": float(nff_s.mean()) if len(nff_s) > 0 else 0.0,
                "std_nff": float(nff_s.std()) if len(nff_s) > 1 else 0.0,
            }

    # Calculate overall broker smart money delta if broker_df provided
    if broker_df is not None and not broker_df.empty and "IDFirm" in broker_df.columns:
        b_df = broker_df.copy()
        if "Date" in b_df.columns:
            b_df["Date"] = pd.to_datetime(b_df["Date"], errors="coerce")
            b_latest = b_df[b_df["Date"] == latest_date]
        else:
            b_latest = b_df

        s_val = float(b_latest[b_latest["IDFirm"].isin(SMART_BROKERS)]["Value"].sum())
        r_val = float(b_latest[b_latest["IDFirm"].isin(RETAIL_BROKERS)]["Value"].sum())
        gen_delta = float(s_val / (r_val + 1e-9))
    else:
        gen_delta = 1.0

    anomalies: list[BandarAnomalyAlert] = []

    for _, row in latest_slice.iterrows():
        ticker = str(row.get("StockCode", ""))
        name = str(row.get("StockName", ticker))
        close_p = float(row.get("Close", 0.0) or 0.0)
        prev_p = float(row.get("Previous", close_p) or close_p)
        vol = float(row.get("Volume", 0.0) or 0.0)
        val = float(row.get("Value", 0.0) or (vol * close_p))
        fb = float(row.get("ForeignBuy", 0.0) or 0.0)
        fs = float(row.get("ForeignSell", 0.0) or 0.0)

        if val < min_turnover_rp or prev_p <= 0 or close_p <= 0:
            continue

        price_chg_pct = (close_p - prev_p) / prev_p * 100.0
        nff_rp = (fb - fs) * close_p
        fb_ratio_pct = (fb / (vol + 1e-9)) * 100.0

        b_stat = baseline_stats.get(ticker)
        if not b_stat:
            continue

        std_vol = (
            b_stat["std_vol"] if b_stat["std_vol"] > 0 else (b_stat["mean_vol"] * 0.4 + 1000.0)
        )
        # Floor std to avoid division by zero or near-zero on illiquid stocks
        std_vol = max(std_vol, b_stat["mean_vol"] * 0.1, 10000.0)
        z_vol = (vol - b_stat["mean_vol"]) / std_vol

        std_val = b_stat["std_val"] if b_stat["std_val"] > 0 else (b_stat["mean_val"] * 0.4 + 1e7)
        std_val = max(std_val, b_stat["mean_val"] * 0.1, 5e7)
        z_val = (val - b_stat["mean_val"]) / std_val

        std_nff = (
            b_stat["std_nff"] if b_stat["std_nff"] > 0 else (abs(b_stat["mean_nff"]) * 0.5 + 1e8)
        )
        std_nff = max(std_nff, 1e8)
        z_nff = (nff_rp - b_stat["mean_nff"]) / std_nff

        # Cap individual Z-scores at 25.0 to maintain clean tabular reporting
        z_vol = max(-25.0, min(25.0, z_vol))
        z_val = max(-25.0, min(25.0, z_val))
        z_nff = max(-25.0, min(25.0, z_nff))

        z_composite = max(z_vol, z_val, z_nff)

        # Check if anomaly crosses 3-sigma cutoff
        if z_composite < sigma_threshold and z_vol < sigma_threshold and z_nff < sigma_threshold:
            continue

        # Classify pattern
        if (
            (z_vol >= sigma_threshold or z_nff >= 2.0)
            and fb_ratio_pct >= 55.0
            and abs(price_chg_pct) <= 1.5
        ):
            anomaly_type = "INSTITUTIONAL_ABSORPTION"
            wyckoff = "Phase C — Silent Absorption / Spring Accumulation"
            headline = f"Whale Absorption detected on {ticker} (+{z_composite:.1f}σ volume spike, flat price)"
            playbook = (
                f"Smart money (Foreign & tier-1 brokers) absorbed {fb_ratio_pct:.1f}% of total volume "
                f"(Net Foreign: Rp {nff_rp / 1e9:+.1f}B) without running up price. Retail supply is being dried up. "
                f"Recommendation: ACCUMULATE / HOLD. Avoid selling into whale bids."
            )
        elif (
            (z_vol >= sigma_threshold or z_nff >= 2.0)
            and fb_ratio_pct >= 60.0
            and price_chg_pct > 1.5
        ):
            anomaly_type = "INSTITUTIONAL_MARKUP"
            wyckoff = "Phase D — Markup Breakout / Sign of Strength (SOS)"
            headline = f"Bullish Institutional Markup on {ticker} (+{price_chg_pct:.1f}% on +{z_vol:.1f}σ vol)"
            playbook = (
                "Aggressive institutional buy aggression lifting ask prices with strong volume expansion. "
                "Recommendation: MOMENTUM BUY / TRAIL STOP. High probability continuation."
            )
        elif (
            z_vol >= sigma_threshold
            and (fb_ratio_pct < 25.0 or z_nff <= -1.5)
            and price_chg_pct > 0.5
        ):
            anomaly_type = "RETAIL_TRAP_DISTRIBUTION"
            wyckoff = "Phase B/C — Upthrust After Distribution (UTAD) / Retail Trap"
            headline = f"Retail Trap warning on {ticker}: Volume spike +{z_vol:.1f}σ on heavy smart money exit"
            playbook = (
                f"Price pushed up while foreign/smart hands are net distributing (NFF: Rp {nff_rp / 1e9:+.1f}B). "
                f"Retail brokers providing exit liquidity. Recommendation: TAKE PROFIT / AVOID CHASING."
            )
        elif z_nff <= -sigma_threshold or (z_vol >= sigma_threshold and z_nff <= -2.0):
            anomaly_type = "INSTITUTIONAL_DUMP"
            wyckoff = "Phase E — Markdown / Institutional Liquidation"
            headline = f"Massive Foreign Dump on {ticker} ({z_nff:.1f}σ negative flow)"
            playbook = (
                f"Heavy institutional selling pressure with Net Foreign Flow Rp {nff_rp / 1e9:+.1f}B. "
                f"Recommendation: DEFENSIVE EXIT / DO NOT CATCH FALLING KNIFE."
            )
        else:
            continue

        alert = BandarAnomalyAlert(
            ticker=ticker,
            company_name=name,
            date=latest_date.strftime("%Y-%m-%d"),
            price=close_p,
            price_change_pct=price_chg_pct,
            volume=vol,
            turnover_rp=val,
            net_foreign_flow_rp=nff_rp,
            foreign_buy_ratio_pct=fb_ratio_pct,
            z_vol=z_vol,
            z_val=z_val,
            z_nff=z_nff,
            z_composite=z_composite,
            anomaly_type=anomaly_type,
            wyckoff_phase=wyckoff,
            smart_money_delta=gen_delta,
            headline=headline,
            playbook=playbook,
        )
        anomalies.append(alert)

    # Sort descending by anomaly severity
    anomalies.sort(key=lambda a: a.z_composite, reverse=True)
    return anomalies


class BandarAnomalyDaemon:
    """Continuous background daemon monitoring 3σ flow anomalies with Telegram dispatch."""

    def __init__(
        self,
        poll_interval_seconds: int = 60,
        sigma_threshold: float = 3.0,
        cooldown_seconds: int = 3600,
        dry_run: bool = False,
    ):
        self.poll_interval = poll_interval_seconds
        self.sigma_threshold = sigma_threshold
        self.cooldown_seconds = cooldown_seconds
        self.dry_run = dry_run
        self.is_running = False
        self._sent_alerts_cache: dict[str, float] = {}  # ticker -> timestamp
        self._recent_alerts: list[dict[str, Any]] = []

    def load_cached_alerts(self) -> list[dict[str, Any]]:
        """Loads historical alert log from disk."""
        if os.path.exists(ALERTS_FILE):
            try:
                return load_json(ALERTS_FILE)
            except Exception:
                return []
        return []

    def save_alerts(self, new_alerts: list[dict[str, Any]]) -> None:
        """Appends new alerts and keeps latest 200 in JSON log."""
        existing = self.load_cached_alerts()
        combined = new_alerts + existing
        trimmed = combined[:200]
        try:
            with open(ALERTS_FILE, "w", encoding="utf-8") as f:
                json.dump(trimmed, f, indent=2)
        except Exception as e:
            log.warning("Could not persist anomaly alerts: %s", e)

    def scan_and_notify(self) -> list[dict[str, Any]]:
        """Performs a single evaluation pass, logging and dispatching eligible alerts."""
        log.info("Running Bandar anomaly scan pass (threshold=%.1fσ)...", self.sigma_threshold)
        anomalies = detect_bandar_anomalies(sigma_threshold=self.sigma_threshold)
        now_ts = time.time()
        dispatched = []

        for a in anomalies:
            last_sent = self._sent_alerts_cache.get(a.ticker, 0.0)
            if now_ts - last_sent < self.cooldown_seconds:
                log.debug("Suppressing alert for %s (cooldown active)", a.ticker)
                continue

            a_dict = a.to_dict()
            msg = a.format_telegram_message()

            if self.dry_run:
                log.info("[DRY-RUN ALERT] %s: %s (Z=%.2f)", a.ticker, a.anomaly_type, a.z_composite)
                print(f"\n{msg}\n")
            else:
                sent = send_telegram_alert(msg)
                a_dict["telegram_delivered"] = sent

            self._sent_alerts_cache[a.ticker] = now_ts
            dispatched.append(a_dict)

        if dispatched:
            self.save_alerts(dispatched)
            log.info("Dispatched %d Bandar anomaly alerts", len(dispatched))

        return dispatched

    async def run_loop(self) -> None:
        """Async daemon loop running periodically."""
        self.is_running = True
        log.info(
            "Starting Bandar Anomaly Notifier Daemon (interval=%ds, threshold=%.1fσ, dry_run=%s)",
            self.poll_interval,
            self.sigma_threshold,
            self.dry_run,
        )
        try:
            while self.is_running:
                try:
                    self.scan_and_notify()
                except Exception as e:
                    log.error("Error in daemon loop: %s", e, exc_info=True)
                await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            log.info("Bandar Anomaly Notifier Daemon stopped gracefully.")
            self.is_running = False
