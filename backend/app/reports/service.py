"""Overflow / missed-collection reports (SPEC Sections 11 and 15)."""
from app.db import now_iso

ACTIVE_STATUSES = ("open", "in_plan")
STATUSES = ("open", "in_plan", "resolved", "rejected")
VERIFIED_ROLES = ("staff", "supervisor")


class ReportConflict(Exception):
    """The report is not in a state that allows this change (HTTP 409)."""


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


def _report_row(conn, report_id: int) -> dict:
    return dict(conn.execute("SELECT * FROM overflow_reports WHERE report_id = ?",
                             (report_id,)).fetchone())


def _mark_missed(conn, bin_id: str) -> bool:
    """If the bin was skipped as below_tau in the latest committed plan, set
    missed=1 on that decision (once). True only when this call set it."""
    plan = conn.execute(
        "SELECT plan_id FROM plans WHERE status = 'committed' "
        "ORDER BY created_at DESC, rowid DESC LIMIT 1").fetchone()
    if plan is None:
        return False
    decision = conn.execute(
        "SELECT decision_id, selected, reason_code, missed FROM pickup_decisions "
        "WHERE plan_id = ? AND bin_id = ? ORDER BY decision_id DESC LIMIT 1",
        (plan["plan_id"], bin_id)).fetchone()
    if (decision is None or decision["selected"] != 0
            or decision["reason_code"] != "below_tau" or decision["missed"] != 0):
        return False
    conn.execute("UPDATE pickup_decisions SET missed = 1 WHERE decision_id = ?",
                 (decision["decision_id"],))
    return True


def create_report(conn, bin_id: str, kind: str, reporter_role: str,
                  photo_path: str | None) -> dict:
    """Insert a report, or merge it into the bin's open/in_plan report. Commits.

    Returns {"report": row, "merged": bool, "missed_collection": bool}.
    Raises LookupError for an unknown bin.
    """
    if conn.execute("SELECT 1 FROM bins WHERE bin_id = ?", (bin_id,)).fetchone() is None:
        raise LookupError(f"Unknown bin {bin_id}")
    verified = 1 if reporter_role in VERIFIED_ROLES else 0
    now = now_iso()
    active = conn.execute(
        "SELECT report_id FROM overflow_reports WHERE bin_id = ? AND status IN (?, ?) "
        "ORDER BY report_id DESC LIMIT 1", (bin_id, *ACTIVE_STATUSES)).fetchone()
    if active is not None:
        report_id = active["report_id"]
        # a merged report keeps its first photo; it takes the new one only if it had none
        conn.execute(
            "UPDATE overflow_reports SET report_count = report_count + 1, updated_at = ?, "
            "verified = MAX(verified, ?), photo_path = COALESCE(photo_path, ?) "
            "WHERE report_id = ?", (now, verified, photo_path, report_id))
    else:
        report_id = conn.execute(
            "INSERT INTO overflow_reports (bin_id, kind, reported_at, updated_at, "
            "reporter_role, photo_path, status, verified, report_count) "
            "VALUES (?, ?, ?, ?, ?, ?, 'open', ?, 1)",
            (bin_id, kind, now, now, reporter_role, photo_path, verified)).lastrowid
    missed = _mark_missed(conn, bin_id)
    conn.commit()
    return {"report": _report_row(conn, report_id), "merged": active is not None,
            "missed_collection": missed}


def reject_report(conn, report_id: int) -> dict:
    """open -> rejected. Commits. Returns the updated row.

    Raises LookupError for an unknown report and ReportConflict if not open.
    """
    row = conn.execute("SELECT status FROM overflow_reports WHERE report_id = ?",
                       (report_id,)).fetchone()
    if row is None:
        raise LookupError(f"Unknown report {report_id}")
    if row["status"] != "open":
        raise ReportConflict(f"Only open reports can be rejected (this one is {row['status']})")
    conn.execute("UPDATE overflow_reports SET status = 'rejected', updated_at = ? "
                 "WHERE report_id = ?", (now_iso(), report_id))
    conn.commit()
    return _report_row(conn, report_id)


def list_reports(conn, status: str = "open") -> dict:
    """{"reports": [row + bin_name]} for one status or "all", newest first."""
    if status != "all" and status not in STATUSES:
        raise ValueError(f"Unknown status {status}")
    rows = conn.execute(
        "SELECT r.*, b.name AS bin_name FROM overflow_reports r "
        "JOIN bins b ON b.bin_id = r.bin_id "
        "WHERE ? = 'all' OR r.status = ? ORDER BY r.report_id DESC",
        (status, status)).fetchall()
    return {"reports": [dict(r) for r in rows]}
