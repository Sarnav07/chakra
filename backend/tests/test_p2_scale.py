"""P2 scale lab backend (SPEC 14 GET/POST /api/scale-lab)."""
import pytest

from app import config
from app.db import get_conn
from app.routing.plan import plan_routes
from app.scale_lab import run as scale_run
from app.selection.select import decide

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
    assert (campus["name"], campus["bins"]) == ("campus", 50)
    assert campus["source"] == "synthetic_fallback"            # test db is not seeded
    # campus uses the recommended fleet size of the same stops (3 if none feasible)
    fallback = scale_run._synthetic_stops(50, 42, 0.006, 0.007, "S")
    recommended = plan_routes(fallback, fleet_sizes=config.FLEET_SIZES,
                              fast=True)["recommended_fleet_size"]
    assert campus["vehicles"] == (recommended or max(config.FLEET_SIZES))
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


def test_campus_uses_tomorrows_selection(seeded_db_path, temp_cache, monkeypatch):
    # campus = the bins decide() selects at the default tau, with the same demand
    monkeypatch.setattr(config, "DB_PATH", seeded_db_path)
    conn = get_conn(seeded_db_path)
    selected = {d["bin_id"]: d["demand_l"]
                for d in decide(conn, config.DEFAULT_TAU)["decisions"] if d["selected"]}
    conn.close()
    stops = {s.bin_id: s.demand_l for s in scale_run._seeded_campus_stops()}
    assert stops.keys() == selected.keys()
    for bin_id, demand in selected.items():
        assert stops[bin_id] == pytest.approx(demand)
    campus = scale_run.run_scale_lab(city_stops=50)["instances"][0]
    assert (campus["source"], campus["bins"]) == ("seeded_db_selection", len(selected))
    assert campus["three_stage"]["feasible"] and campus["nearest_neighbor"]["feasible"]
