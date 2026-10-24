"""Selection decisions for the dispatcher."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import math

from app import config
from app.db import get_meta
from app.reports.service import active_reports_by_bin


def p_overflow_from_quantiles(current, inc_p10, inc_p50, inc_p90) -> float | None:
    if current is None or inc_p10 is None or inc_p50 is None or inc_p90 is None:
        return None
    sigma = max((inc_p90 - inc_p10) / 2.563, 1.0)
    z = (100.0 - (current + inc_p50)) / sigma
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def classify_bin(current_fill_pct, p_overflow, is_stale, open_report, tau):
    if not config.TAU_MIN <= tau <= config.TAU_MAX:
        raise ValueError(f"tau must be between {config.TAU_MIN} and {config.TAU_MAX}")
    if current_fill_pct is not None and current_fill_pct >= config.OVERFLOW_PCT:
        return True, "overflowing_now"
    if open_report:
        return True, "reported"
    if is_stale or current_fill_pct is None or p_overflow is None:
        return True, "needs_review"
    if p_overflow > tau:
        return True, "p_over_tau"
    return False, "below_tau"


def decide(conn, tau: float, plan_date: date | None = None) -> dict:
    """Return forecast-backed decisions and a dispatcher summary, without writes."""
    from app.forecast.model import forecast_bins

    if not config.TAU_MIN <= tau <= config.TAU_MAX:
        raise ValueError(f"tau must be between {config.TAU_MIN} and {config.TAU_MAX}")
    scenario_now_raw = get_meta(conn, "scenario_now")
    if scenario_now_raw is None:
        raise ValueError("Database not seeded - run python -m app.seed")
    plan_date = plan_date or date.fromisoformat(get_meta(conn, "plan_date") or "")
    scenario_now = datetime.fromisoformat(scenario_now_raw)
    forecasts = {r["bin_id"]: r for r in forecast_bins(conn, plan_date)}
    observations = {
        r["bin_id"]: r for r in conn.execute(
            "SELECT o.* FROM fill_observations o JOIN "
            "(SELECT bin_id,MAX(obs_id) obs_id FROM fill_observations GROUP BY bin_id) x "
            "ON o.obs_id=x.obs_id"
        )
    }
    active_reports = active_reports_by_bin(conn)

    result = []
    counts = {key: 0 for key in ("selected", "skipped", "needs_review", "reported", "overflowing_now")}
    skipped_probabilities = []
    for bin_row in conn.execute("SELECT * FROM bins ORDER BY bin_id"):
        bin_data = dict(bin_row)
        obs = observations.get(bin_data["bin_id"])
        current = float(obs["fill_pct"]) if obs is not None else None
        stale = obs is None or datetime.fromisoformat(obs["observed_at"]) < (
            scenario_now - timedelta(hours=config.STALE_HOURS)
        )
        fc = forecasts.get(bin_data["bin_id"], {})
        p = fc.get("p_overflow")
        report = active_reports.get(bin_data["bin_id"])
        selected, reason_code = classify_bin(current, p, stale, report is not None, tau)
        if reason_code == "overflowing_now":
            reason = f"Overflowing now (last reading {current:.0f}%)"
        elif reason_code == "reported":
            kind_text = "overflow" if report["kind"] == "overflow" else "missed pickup"
            reason = f"Reported {kind_text} by {report['reporter_role']} - {report['status']}"
        elif reason_code == "needs_review":
            reason = "No fresh reading in 36 h - visit and tap a level"
        elif reason_code == "p_over_tau":
            reason = f"{p:.0%} chance of overflow tomorrow, above tau = {tau:.2f}"
        else:
            reason = f"{p:.0%} chance of overflow tomorrow, below tau = {tau:.2f}"
        capacity = float(bin_data["capacity_l"])
        demand_l = capacity * config.STALE_DEMAND_PCT / 100 if stale and current is None else (
            capacity * max(current or 0.0, config.MIN_DEMAND_PCT) / 100
        )
        counts["selected"] += int(selected)
        if reason_code == "below_tau":
            counts["skipped"] += 1
            if p is not None:
                skipped_probabilities.append(float(p))
        if reason_code in counts and reason_code not in ("selected", "skipped"):
            counts[reason_code] += 1
        result.append({
            **bin_data,
            "current_fill_pct": current,
            "predicted_fill_pct": fc.get("predicted_fill_pct"),
            "p_overflow": p,
            "selected": selected,
            "reason_code": reason_code,
            "reason": reason,
            "report_id": report["report_id"] if report else None,
            "demand_l": demand_l if selected else 0.0,
            "demand_uncertain": True,
        })
    result.sort(key=lambda row: (
        not row["selected"], row["p_overflow"] is None,
        -(row["p_overflow"] or 0.0), row["bin_id"],
    ))
    return {
        "plan_date": plan_date.isoformat(),
        "tau": float(tau),
        "decisions": result,
        "summary": {**counts, "expected_overflows_skipped": round(sum(skipped_probabilities), 2)},
    }
