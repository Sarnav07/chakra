"""Configuration constants (SPEC Section 6).

All values are SYNTHETIC ASSUMPTIONS for the prototype.
"""
import os
from datetime import timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=5, minutes=30))
TZ_LABEL = "UTC+05:30 (IST)"

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = Path(os.environ.get("CHAKRA_DB_PATH", DATA_DIR / "chakra.db"))
DEMO_CACHE_DIR = DATA_DIR / "demo_cache"
UPLOAD_DIR = DATA_DIR / "uploads"
MODEL_DIR = DATA_DIR / "model"

SEED = 42
CAMPUS_CENTER = (29.8650, 77.8960)   # approximate; synthetic layout
NODES = [
    {"node_id": "DEPOT", "name": "Depot (synthetic)", "kind": "depot",
     "lat": 29.8628, "lon": 77.8935},
    {"node_id": "COMPOST", "name": "Compost stop (synthetic)", "kind": "compost",
     "lat": 29.8672, "lon": 77.8990}]
VEHICLES = [
    {"vehicle_id": "V1", "capacity_l": 4000, "fixed_cost_rs": 800, "cost_per_km_rs": 12},
    {"vehicle_id": "V2", "capacity_l": 4000, "fixed_cost_rs": 800, "cost_per_km_rs": 12},
    {"vehicle_id": "V3", "capacity_l": 4000, "fixed_cost_rs": 800, "cost_per_km_rs": 12}]
FLEET_SIZES = (1, 2, 3)
DETOUR_FACTOR = 1.3          # road km = straight-line km x 1.3
SPEED_KMPH = 15
SERVICE_MIN_PER_BIN = 3
SHIFT_MIN = 300
CAPACITY_BUFFER = 0.9        # plan loads up to 90% of vehicle capacity
LEVEL_PCT = {"low": 25, "medium": 60, "full": 90}
OVERFLOW_PCT = 100
STALE_HOURS = 36
DEFAULT_TAU = 0.5
TAU_MIN = 0.05
TAU_MAX = 0.95
MIN_DEMAND_PCT = 10          # selected bins carry at least 10% of capacity
STALE_DEMAND_PCT = 50        # assumed demand for a bin with no reading
FOOD_DENSITY_KG_PER_L = 0.6
CLASSIFIER_CONFIDENCE_MIN = 0.6
MAX_UPLOAD_MB = 8
ORTOOLS_TIME_LIMIT_S = 1     # per cluster, interactive mode only


def scenario_assumptions() -> dict:
    """The "assumptions" block returned by /api/scenario (also reused by routes and twin)."""
    return {
        "detour_factor": DETOUR_FACTOR,
        "speed_kmph": SPEED_KMPH,
        "service_min_per_bin": SERVICE_MIN_PER_BIN,
        "shift_min": SHIFT_MIN,
        "capacity_buffer": CAPACITY_BUFFER,
        "level_pct": dict(LEVEL_PCT),
        "stale_hours": STALE_HOURS,
        "food_density_kg_per_l": FOOD_DENSITY_KG_PER_L,
        "tau_default": DEFAULT_TAU,
        "tau_min": TAU_MIN,
        "tau_max": TAU_MAX,
    }
