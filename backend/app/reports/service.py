"""Overflow / missed-collection report helpers (SPEC Sections 11 and 15)."""
from app.db import now_iso

ACTIVE_STATUSES = ("open", "in_plan")


def active_reports_by_bin(conn) -> dict[str, dict]:
    """Reports with status open or in_plan, keyed by bin_id."""
    rows = conn.execute(
        "SELECT * FROM overflow_reports WHERE status IN (?, ?) ORDER BY report_id",
        ACTIVE_STATUSES).fetchall()
    return {row["bin_id"]: dict(row) for row in rows}


def mark_in_plan(conn, bin_ids: list[str]) -> None:
    """open -> in_plan for the given bins (a committed plan includes them). Commits."""
    if not bin_ids:
        return
    marks = ",".join("?" * len(bin_ids))
    conn.execute(
        f"UPDATE overflow_reports SET status = 'in_plan', updated_at = ? "
        f"WHERE status = 'open' AND bin_id IN ({marks})",
        (now_iso(), *bin_ids))
    conn.commit()


def mark_resolved(conn, bin_id: str) -> int:
    """open/in_plan -> resolved for one bin (its pickup was confirmed). Commits.

    The commit also commits any earlier uncommitted statements on this
    connection, so a caller building one transaction should call this last.
    Returns the number of reports resolved.
    """
    cur = conn.execute(
        "UPDATE overflow_reports SET status = 'resolved', updated_at = ? "
        "WHERE bin_id = ? AND status IN (?, ?)",
        (now_iso(), bin_id, *ACTIVE_STATUSES))
    conn.commit()
    return cur.rowcount
