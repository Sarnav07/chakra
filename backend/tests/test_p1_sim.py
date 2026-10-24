"""P1 synthetic scenario acceptance checks."""

from datetime import date, datetime, timedelta

from app import config
from app.db import get_conn
from app.seed import run_seed


def test_seed_layout_history_and_stale_demo_bins(seeded_db_path):
    conn = get_conn(seeded_db_path)
    try:
        rows = list(conn.execute("SELECT bin_id,group_type FROM bins ORDER BY bin_id"))
        assert len(rows) == 50
        assert {key: sum(r["group_type"] == key for r in rows) for key in (
            "hostel", "mess", "mess_food", "department"
        )} == {"hostel": 30, "mess": 6, "mess_food": 6, "department": 8}
        assert {r["bin_id"] for r in rows} == (
            {f"H{letter}-{number}" for letter in "ABCDEF" for number in range(1, 6)}
            | {f"M{mess}-{kind}{number}" for mess in range(1, 4)
               for kind in ("G", "F") for number in range(1, 3)}
            | {f"D{department}-{number}" for department in range(1, 5)
               for number in range(1, 3)}
        )
        meta = {r["key"]: r["value"] for r in conn.execute("SELECT * FROM meta")}
        assert {"scenario_date", "plan_date", "scenario_now", "seed", "created_at", "data_label"} <= set(meta)
        assert meta["plan_date"] == (date.fromisoformat(meta["scenario_date"]) + timedelta(days=1)).isoformat()
        assert meta["data_label"] == "simulated"
        assert conn.execute("SELECT COUNT(*) FROM mess_waste_logs").fetchone()[0] == 1620
        assert conn.execute("SELECT COUNT(*) FROM pickup_events WHERE route_id NOT LIKE 'HIST-%'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM fill_observations WHERE fill_pct NOT BETWEEN 0 AND 100").fetchone()[0] == 0
        cutoff = datetime.fromisoformat(meta["scenario_now"]) - timedelta(hours=config.STALE_HOURS)
        last = list(conn.execute(
            "SELECT b.bin_id,MAX(o.observed_at) AS last_at FROM bins b "
            "LEFT JOIN fill_observations o ON b.bin_id=o.bin_id GROUP BY b.bin_id"
        ))
        stale = [r["bin_id"] for r in last if r["last_at"] is None
                 or datetime.fromisoformat(r["last_at"]) < cutoff]
        assert len(stale) == 2
    finally:
        conn.close()


def test_seed_reproducible_observations(tmp_path):
    paths = [tmp_path / f"seed-{index}.db" for index in range(3)]
    for path, seed in zip(paths, (42, 42, 43)):
        run_seed(seed=seed, scenario_date=date(2026, 10, 24), db_path=path)
    samples = []
    for path in paths:
        conn = get_conn(path)
        try:
            samples.append([
                tuple(row) for row in conn.execute(
                    "SELECT bin_id,observed_at,fill_pct FROM fill_observations ORDER BY obs_id"
                )
            ])
        finally:
            conn.close()
    assert samples[0] == samples[1]
    assert samples[0] != samples[2]
