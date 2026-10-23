# STUB created by P2 - owner P1 replaces this file
"""Bin selection rules (SPEC Section 9)."""
import datetime


def p_overflow_from_quantiles(current, inc_p10, inc_p50, inc_p90) -> float:
    """P(fill >= 100) by the end of plan_date."""
    raise NotImplementedError("STUB - owner P1 implements this")


def classify_bin(current_fill_pct, p_overflow, is_stale, open_report,
                 tau) -> tuple[bool, str]:
    """Return (selected, reason_code) for one bin."""
    raise NotImplementedError("STUB - owner P1 implements this")


def decide(conn, tau: float, plan_date: datetime.date | None = None) -> dict:
    """The POST /api/decisions response body."""
    raise NotImplementedError("STUB - owner P1 implements this")
