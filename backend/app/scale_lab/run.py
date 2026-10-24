"""Scale lab: three-stage routing vs nearest neighbour on a campus and a city
instance (SPEC 14 GET/POST /api/scale-lab). All city data is synthetic."""
import json
import sqlite3
import time

import numpy as np

from app import config
from app.config import (CAMPUS_CENTER, DEMO_CACHE_DIR, MIN_DEMAND_PCT, STALE_DEMAND_PCT)
from app.db import get_conn, get_meta, now_iso
from app.routing.plan import baseline_nearest_neighbor, plan_routes
from app.routing.types import RoutingSettings, Stop

CACHE_NAME = "scale_lab.json"
CAMPUS_FLEET_IF_NONE = max(config.FLEET_SIZES)   # campus fleet if no size is feasible
SYNTHETIC_CAPACITY_L = 240
CITY_HALF_SPAN_DEG = 0.045          # +/- 0.045 deg lat/lon, about 10 x 10 km
CITY_VEHICLES = [{"vehicle_id": f"C{i:02d}", "capacity_l": 10000, "fixed_cost_rs": 800,
                  "cost_per_km_rs": 12} for i in range(1, 31)]
CITY_SETTINGS = dict(speed_kmph=25, service_min_per_bin=1.5, shift_min=600)


def _cache_path():
    return DEMO_CACHE_DIR / CACHE_NAME


def _synthetic_stops(n, seed, half_lat, half_lon, prefix) -> list[Stop]:
    """n general stops, capacity 240 L, demand 20-90 % of capacity."""
    rng = np.random.default_rng(seed)
    lats = CAMPUS_CENTER[0] + rng.uniform(-half_lat, half_lat, n)
    lons = CAMPUS_CENTER[1] + rng.uniform(-half_lon, half_lon, n)
    demand = SYNTHETIC_CAPACITY_L * rng.uniform(0.2, 0.9, n)
    width = len(str(n))
    return [Stop(bin_id=f"{prefix}{i + 1:0{width}d}", name=f"Synthetic stop {i + 1}",
                 lat=float(lats[i]), lon=float(lons[i]), stream="general",
                 demand_l=float(demand[i])) for i in range(n)]


def _seeded_campus_stops() -> list[Stop] | None:
    """All bins of the main database as stops, or None if it is not seeded.
    Demand = capacity x max(latest fill, MIN_DEMAND_PCT) / 100; a bin with no
    reading uses STALE_DEMAND_PCT (as SPEC 9)."""
    if not config.DB_PATH.exists():
        return None
    conn = get_conn(config.DB_PATH)
    try:
        if not get_meta(conn, "scenario_date"):
            return None
        rows = conn.execute(
            "SELECT b.*, (SELECT o.fill_pct FROM fill_observations o WHERE o.bin_id = b.bin_id "
            "ORDER BY o.obs_id DESC LIMIT 1) AS latest_fill FROM bins b ORDER BY b.bin_id"
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    stops = []
    for r in rows:
        pct = STALE_DEMAND_PCT if r["latest_fill"] is None else max(r["latest_fill"], MIN_DEMAND_PCT)
        stops.append(Stop(bin_id=r["bin_id"], name=r["name"], lat=r["lat"], lon=r["lon"],
                          stream=r["stream"], demand_l=r["capacity_l"] * pct / 100))
    return stops or None


def _campus_fleet_size(stops, settings) -> int:
    """Recommended fleet size over FLEET_SIZES (SPEC 10), or CAMPUS_FLEET_IF_NONE."""
    planned = plan_routes(stops, fleet_sizes=config.FLEET_SIZES, fast=True, settings=settings)
    return planned["recommended_fleet_size"] or CAMPUS_FLEET_IF_NONE


def _measure(name, stops, fleet_size, settings, source) -> dict:
    """Time plan_routes(fast=True) and the nearest-neighbour baseline on the same stops."""
    t0 = time.perf_counter()
    alt = plan_routes(stops, fleet_sizes=(fleet_size,), fast=True,
                      settings=settings)["alternatives"][0]
    three_stage_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    nn = baseline_nearest_neighbor(stops, fleet_size, settings)
    nn_s = time.perf_counter() - t0
    return {"name": name, "bins": len(stops), "vehicles": fleet_size, "source": source,
            "three_stage": {"km": round(float(alt["total_km"]), 3),
                            "runtime_s": round(three_stage_s, 3),
                            "feasible": bool(alt["feasible"])},
            "nearest_neighbor": {"km": round(float(nn["total_km"]), 3),
                                 "runtime_s": round(nn_s, 3),
                                 "feasible": bool(nn["feasible"])}}


def run_scale_lab(city_stops: int = 2000) -> dict:
    """Run both instances, write DEMO_CACHE_DIR/scale_lab.json and return it."""
    campus = _seeded_campus_stops()
    source = "seeded_db"
    if campus is None:
        campus = _synthetic_stops(50, 42, 0.006, 0.007, "S")
        source = "synthetic_fallback"
    city = _synthetic_stops(city_stops, 7, CITY_HALF_SPAN_DEG, CITY_HALF_SPAN_DEG, "C")
    city_settings = RoutingSettings(vehicles=[dict(v) for v in CITY_VEHICLES], **CITY_SETTINGS)
    campus_settings = RoutingSettings()
    campus_k = _campus_fleet_size(campus, campus_settings)

    result = {"generated_at": now_iso(), "synthetic": True, "instances": [
        _measure("campus", campus, campus_k, campus_settings, source),
        _measure("city", city, len(CITY_VEHICLES), city_settings, "synthetic"),
    ]}
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def load_scale_cache() -> dict | None:
    """Contents of DEMO_CACHE_DIR/scale_lab.json, or None if it does not exist."""
    path = _cache_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
