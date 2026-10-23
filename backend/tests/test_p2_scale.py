"""P2 scale lab backend (SPEC 14 GET/POST /api/scale-lab)."""
import pytest

from app import config
from app.db import set_meta
from app.scale_lab import run as scale_run

METRIC_KEYS = {"km", "runtime_s", "feasible"}


@pytest.fixture
def temp_cache(tmp_path, monkeypatch, db_path):
    """Cache in a temp folder; the "main" database is the empty test db."""
    monkeypatch.setattr(scale_run, "DEMO_CACHE_DIR", tmp_path / "demo_cache")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    return tmp_path / "demo_cache"


def test_get_before_any_run_is_404(client, temp_cache):
    r = client.get("/api/scale-lab")
    assert r.status_code == 404
    assert r.json() == {"detail": "Scale lab not cached - run POST /api/scale-lab/run"}


def test_run_small_returns_both_instances(client, temp_cache):
    result = scale_run.run_scale_lab(city_stops=200)
    assert set(result) == {"generated_at", "synthetic", "instances"}
    assert result["synthetic"] is True
    campus, city = result["instances"]
    assert (campus["name"], campus["bins"], campus["vehicles"]) == ("campus", 50, 2)
    assert campus["source"] == "synthetic_fallback"            # test db is not seeded
    assert (city["name"], city["bins"], city["vehicles"]) == ("city", 200, 30)
    for inst in result["instances"]:
        assert set(inst) == {"name", "bins", "vehicles", "source", "three_stage",
                             "nearest_neighbor"}
        for method in ("three_stage", "nearest_neighbor"):
            assert set(inst[method]) == METRIC_KEYS
            assert isinstance(inst[method]["km"], float) and inst[method]["km"] >= 0
            assert inst[method]["runtime_s"] >= 0
            assert isinstance(inst[method]["feasible"], bool)
    # the cache was written and GET returns it
    assert (temp_cache / "scale_lab.json").exists()
    assert client.get("/api/scale-lab").json() == result


def test_campus_uses_seeded_db_bins(conn, temp_cache):
    conn.executemany("INSERT INTO bins VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
        ("HA-1", "Hostel A bin 1", "hostel", "Hostel A", "general", 29.8661, 77.8942, 240),
        ("M1-F1", "Mess 1 food bin 1", "mess_food", "Mess 1", "food", 29.8647, 77.8984, 120),
        ("D1-1", "Dept 1 bin 1", "department", "Dept 1", "general", 29.8633, 77.8955, 120)])
    conn.executemany("INSERT INTO fill_observations (bin_id, observed_at, fill_pct, source) "
                     "VALUES (?, '2026-10-24T20:00:00+05:30', ?, 'simulated')",
                     [("HA-1", 80.0), ("M1-F1", 5.0)])          # D1-1 has no reading
    conn.commit()
    set_meta(conn, "scenario_date", "2026-10-24")
    stops = {s.bin_id: s for s in scale_run._seeded_campus_stops()}
    assert stops["HA-1"].demand_l == pytest.approx(240 * 0.80)
    assert stops["M1-F1"].demand_l == pytest.approx(120 * 0.10)      # max(5, 10) %
    assert stops["D1-1"].demand_l == pytest.approx(120 * 0.50)       # no reading
    campus = scale_run.run_scale_lab(city_stops=50)["instances"][0]
    assert (campus["source"], campus["bins"]) == ("seeded_db", 3)
