"""
Crash Detector — detects sudden/abnormal market movements.

Checks:
  - Rapid price drop
  - Volume spike
  - VIX spike
  - Bid-ask spread widening
  - TSE circuit breaker status
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# TSE circuit breaker thresholds (simplified — actual rules vary by price range)
_TSE_CB_THRESHOLDS = {
    "limit_up": 0.30,    # +30% daily limit
    "limit_down": -0.30, # -30% daily limit
}


class CrashDetector:
    """Detects sudden market crashes, corrections, and anomalies."""

    def __init__(
        self,
        drop_threshold: float = -3.0,
        spike_threshold: float = 5.0,
    ) -> None:
        """
        Args:
            drop_threshold: Percentage drop that signals a crash (negative number).
            spike_threshold: VIX/volume multiplier that signals abnormality.
        """
        self.drop_threshold = drop_threshold
        self.spike_threshold = spike_threshold

    def check_market(self, market_data: dict) -> dict:
        """
        Analyse market data for crash signals.

        Args:
            market_data: Dict with optional keys:
              - price_change_pct (float): current session price change %
              - volume_ratio (float): current volume / average volume
              - vix (float): VIX or 日経VI value
              - vix_change_pct (float): VIX change from previous close %
              - bid_ask_spread (float): current spread
              - avg_bid_ask_spread (float): normal spread
              - intraday_low_pct (float): intraday drop from open %

        Returns:
            Dict with:
              - is_crash (bool)
              - severity (str): "normal" / "warning" / "severe" / "extreme"
              - type (str | None): "flash_crash" / "correction" / "black_swan"
              - recommended_action (str)
              - signals (list[str]): individual triggered signals
        """
        signals: list[str] = []
        severity_score = 0

        # 1. Rapid price drop
        price_change = market_data.get("price_change_pct", 0.0)
        if price_change <= self.drop_threshold:
            signals.append(f"Price drop {price_change:.1f}% (threshold {self.drop_threshold:.1f}%)")
            severity_score += 2
        if price_change <= self.drop_threshold * 2:
            severity_score += 3  # extreme drop

        # 2. Intraday flash move
        intraday_low = market_data.get("intraday_low_pct", 0.0)
        if intraday_low <= self.drop_threshold:
            signals.append(f"Intraday low {intraday_low:.1f}% from open")
            severity_score += 2

        # 3. Volume spike
        volume_ratio = market_data.get("volume_ratio", 1.0)
        if volume_ratio >= self.spike_threshold:
            signals.append(f"Volume spike {volume_ratio:.1f}x average")
            severity_score += 1

        # 4. VIX / 日経VI spike
        vix = market_data.get("vix", 0.0)
        vix_change = market_data.get("vix_change_pct", 0.0)
        if vix >= 30:
            signals.append(f"VIX elevated: {vix:.1f}")
            severity_score += 2
        if vix >= 40:
            severity_score += 2
        if vix_change >= 20:
            signals.append(f"VIX spike +{vix_change:.1f}%")
            severity_score += 2

        # 5. Bid-ask spread widening
        spread = market_data.get("bid_ask_spread", 0.0)
        avg_spread = market_data.get("avg_bid_ask_spread", 0.0)
        if avg_spread > 0 and spread > 0:
            spread_ratio = spread / avg_spread
            if spread_ratio >= self.spike_threshold:
                signals.append(f"Spread widened {spread_ratio:.1f}x normal")
                severity_score += 1

        # Determine severity
        if severity_score >= 7:
            severity = "extreme"
        elif severity_score >= 4:
            severity = "severe"
        elif severity_score >= 2:
            severity = "warning"
        else:
            severity = "normal"

        # Determine crash type
        crash_type: str | None = None
        is_crash = severity_score >= 2

        if is_crash:
            if (intraday_low <= self.drop_threshold and
                    volume_ratio >= self.spike_threshold):
                crash_type = "flash_crash"
            elif severity_score >= 7:
                crash_type = "black_swan"
            else:
                crash_type = "correction"

        # Recommended action
        if severity == "extreme":
            action = "Flatten all positions immediately. Do not re-enter."
        elif severity == "severe":
            action = "Close speculative positions. Keep only hedged positions."
        elif severity == "warning":
            action = "Reduce position sizes by 50%. Tighten stops."
        else:
            action = "Continue normal trading."

        result = {
            "is_crash": is_crash,
            "severity": severity,
            "type": crash_type,
            "recommended_action": action,
            "signals": signals,
        }

        if is_crash:
            logger.warning("CRASH DETECTED [%s]: %s — %s", severity, crash_type, signals)

        return result

    def check_circuit_breaker_triggered(self, market_data: dict) -> bool:
        """
        Check if the TSE circuit breaker (ストップ高/ストップ安) has been hit.

        Args:
            market_data: Dict with "price_change_pct" (daily % change).

        Returns:
            True if the exchange-level circuit breaker is likely triggered.
        """
        price_change = market_data.get("price_change_pct", 0.0)

        if price_change >= _TSE_CB_THRESHOLDS["limit_up"] * 100:
            logger.warning("TSE CIRCUIT BREAKER: ストップ高 (limit up) — %.1f%%", price_change)
            return True

        if price_change <= _TSE_CB_THRESHOLDS["limit_down"] * 100:
            logger.warning("TSE CIRCUIT BREAKER: ストップ安 (limit down) — %.1f%%", price_change)
            return True

        return False
