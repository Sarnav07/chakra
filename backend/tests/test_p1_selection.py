"""P1 overflow probability and dispatcher selection checks."""

from app.db import get_conn
from app.selection.select import classify_bin, decide, p_overflow_from_quantiles


def test_probability_and_priority_rules():
    low = p_overflow_from_quantiles(20, 30, 40, 50)
    high = p_overflow_from_quantiles(75, 20, 30, 40)
    assert classify_bin(20, low, False, False, 0.5) == (False, "below_tau")
    assert classify_bin(75, high, False, False, 0.5) == (True, "p_over_tau")
    assert classify_bin(None, None, True, False, 0.5) == (True, "needs_review")
    assert classify_bin(100, high, True, True, 0.5) == (True, "overflowing_now")
    assert classify_bin(20, low, False, True, 0.5) == (True, "reported")


def test_decisions_report_priority_sort_and_summary(seeded_db_path):
    conn = get_conn(seeded_db_path)
    try:
        initial = decide(conn, 0.5)
        assert len(initial["decisions"]) == 50
        assert initial["summary"]["selected"] + initial["summary"]["skipped"] == 50
        assert initial["summary"]["needs_review"] == 2
        target = next(row for row in initial["decisions"] if row["reason_code"] == "below_tau")
        conn.execute(
            "INSERT INTO overflow_reports(bin_id,kind,reported_at,updated_at,reporter_role,status,verified) "
            "VALUES (?, 'overflow', '2026-10-24T20:15:00+05:30', "
            "'2026-10-24T20:15:00+05:30', 'qr', 'open', 0)", (target["bin_id"],),
        )
        conn.commit()
        updated = decide(conn, 0.5)
        reported = next(row for row in updated["decisions"] if row["bin_id"] == target["bin_id"])
        assert (reported["selected"], reported["reason_code"]) == (True, "reported")
        assert reported["report_id"] is not None
        assert [row["selected"] for row in updated["decisions"]] == sorted(
            (row["selected"] for row in updated["decisions"]), reverse=True
        )
        skipped = [row["p_overflow"] for row in updated["decisions"]
                   if row["reason_code"] == "below_tau"]
        assert updated["summary"]["expected_overflows_skipped"] == round(sum(skipped), 2)
        assert updated["summary"]["selected"] + updated["summary"]["skipped"] == 50

        conn.execute(
            "INSERT INTO fill_observations(bin_id,observed_at,fill_pct,source) "
            "VALUES (?, '2026-10-24T20:20:00+05:30', 100, 'staff_tap')",
            (target["bin_id"],),
        )
        conn.commit()
        overflowing = next(row for row in decide(conn, 0.5)["decisions"]
                           if row["bin_id"] == target["bin_id"])
        assert overflowing["reason_code"] == "overflowing_now"
    finally:
        conn.close()


def test_tau_api_bounds(seeded_client):
    for tau in (0.05, 0.95):
        assert seeded_client.post("/api/decisions", json={"tau": tau}).status_code == 200
    for tau in (0, 1):
        assert seeded_client.post("/api/decisions", json={"tau": tau}).status_code == 422
