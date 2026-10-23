# STUB created by P2 - owner P1 replaces this file
"""Fill forecast model (SPEC Section 9)."""
import datetime


def forecast_bins(conn, plan_date: datetime.date) -> list[dict]:
    """Forecast every bin for plan_date (not stored)."""
    raise NotImplementedError("STUB - owner P1 implements this")


def persist_forecasts(conn, forecasts: list[dict]) -> list[dict]:
    """Store forecasts; return them with forecast_id."""
    raise NotImplementedError("STUB - owner P1 implements this")


def evaluate(conn) -> dict:
    """Time-split evaluation report."""
    raise NotImplementedError("STUB - owner P1 implements this")
