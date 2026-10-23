"""SQLite connection helpers and schema (SPEC Section 7)."""
import sqlite3
from datetime import datetime
from pathlib import Path

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS bins (
  bin_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  group_type TEXT NOT NULL CHECK (group_type IN ('hostel','mess','department','mess_food')),
  group_name TEXT NOT NULL,
  stream TEXT NOT NULL CHECK (stream IN ('general','food')),
  lat REAL NOT NULL, lon REAL NOT NULL,
  capacity_l INTEGER NOT NULL CHECK (capacity_l > 0));

CREATE TABLE IF NOT EXISTS nodes (
  node_id TEXT PRIMARY KEY, name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('depot','compost')),
  lat REAL NOT NULL, lon REAL NOT NULL);

CREATE TABLE IF NOT EXISTS vehicles (
  vehicle_id TEXT PRIMARY KEY, capacity_l INTEGER NOT NULL,
  fixed_cost_rs REAL NOT NULL, cost_per_km_rs REAL NOT NULL);

CREATE TABLE IF NOT EXISTS fill_observations (
  obs_id INTEGER PRIMARY KEY AUTOINCREMENT,
  bin_id TEXT NOT NULL REFERENCES bins(bin_id),
  observed_at TEXT NOT NULL,
  fill_pct REAL NOT NULL CHECK (fill_pct >= 0 AND fill_pct <= 100),
  source TEXT NOT NULL CHECK (source IN ('simulated','staff_tap','camera','pickup_reset')),
  quality TEXT NOT NULL DEFAULT 'ok' CHECK (quality IN ('ok','suspect')));
CREATE INDEX IF NOT EXISTS ix_obs_bin ON fill_observations(bin_id, obs_id);

CREATE TABLE IF NOT EXISTS fill_forecasts (
  forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
  bin_id TEXT NOT NULL REFERENCES bins(bin_id),
  created_at TEXT NOT NULL, plan_date TEXT NOT NULL, horizon_end TEXT NOT NULL,
  current_fill_pct REAL, predicted_increment_pct REAL, predicted_fill_pct REAL,
  p10_fill_pct REAL, p90_fill_pct REAL,
  p_overflow REAL CHECK (p_overflow IS NULL OR (p_overflow >= 0 AND p_overflow <= 1)),
  model_version TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS plans (
  plan_id TEXT PRIMARY KEY, plan_date TEXT NOT NULL, tau REAL NOT NULL,
  created_at TEXT NOT NULL, chosen_fleet_size INTEGER,
  status TEXT NOT NULL CHECK (status IN ('draft','committed','superseded')),
  response_json TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS route_plans (
  route_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plans(plan_id),
  fleet_size INTEGER NOT NULL, vehicle_id TEXT NOT NULL,
  stream TEXT NOT NULL CHECK (stream IN ('general','food')),
  start_node TEXT NOT NULL, end_node TEXT NOT NULL,
  ordered_bin_ids TEXT NOT NULL,          -- JSON array of bin_id
  km REAL NOT NULL, minutes REAL NOT NULL, load_l REAL NOT NULL,
  est_cost_rs REAL NOT NULL, feasible INTEGER NOT NULL CHECK (feasible IN (0,1)));

CREATE TABLE IF NOT EXISTS pickup_decisions (
  decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id TEXT NOT NULL REFERENCES plans(plan_id),
  plan_date TEXT NOT NULL, bin_id TEXT NOT NULL REFERENCES bins(bin_id),
  tau REAL NOT NULL, selected INTEGER NOT NULL CHECK (selected IN (0,1)),
  reason_code TEXT NOT NULL CHECK (reason_code IN
    ('overflowing_now','reported','needs_review','p_over_tau','below_tau')),
  reason TEXT NOT NULL, p_overflow REAL, forecast_id INTEGER, report_id INTEGER,
  missed INTEGER NOT NULL DEFAULT 0 CHECK (missed IN (0,1)),
  created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS pickup_events (
  pickup_id INTEGER PRIMARY KEY AUTOINCREMENT,
  route_id TEXT NOT NULL, bin_id TEXT NOT NULL REFERENCES bins(bin_id),
  completed_at TEXT NOT NULL, collected_volume_l REAL NOT NULL,
  level TEXT CHECK (level IS NULL OR level IN ('low','medium','full')),
  staff_note TEXT,
  UNIQUE (route_id, bin_id));
  -- history pickups written by the seed use route_id 'HIST-YYYY-MM-DD'
  -- (no foreign key on route_id because history routes are not in route_plans)

CREATE TABLE IF NOT EXISTS batch_events (
  batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  source_pickup_ids TEXT NOT NULL,        -- JSON array, one pickup_id
  stream TEXT NOT NULL CHECK (stream IN ('general','food')),
  destination TEXT NOT NULL CHECK (destination IN ('depot','compost_stop')),
  status TEXT NOT NULL CHECK (status IN ('pending_handoff','delivered_to_compost')),
  volume_l REAL NOT NULL);

CREATE TABLE IF NOT EXISTS overflow_reports (
  report_id INTEGER PRIMARY KEY AUTOINCREMENT,
  bin_id TEXT NOT NULL REFERENCES bins(bin_id),
  kind TEXT NOT NULL CHECK (kind IN ('overflow','missed_collection')),
  reported_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  reporter_role TEXT NOT NULL CHECK (reporter_role IN ('staff','qr','supervisor')),
  photo_path TEXT,
  status TEXT NOT NULL CHECK (status IN ('open','in_plan','resolved','rejected')),
  verified INTEGER NOT NULL CHECK (verified IN (0,1)),
  report_count INTEGER NOT NULL DEFAULT 1);

CREATE TABLE IF NOT EXISTS item_checks (
  check_id INTEGER PRIMARY KEY AUTOINCREMENT,
  image_path TEXT NOT NULL, predicted_class TEXT NOT NULL,
  confidence REAL NOT NULL, hazardous INTEGER NOT NULL CHECK (hazardous IN (0,1)),
  unsure INTEGER NOT NULL CHECK (unsure IN (0,1)),
  suggested_bin TEXT, model_version TEXT NOT NULL,
  checked_at TEXT NOT NULL, bin_id TEXT);

CREATE TABLE IF NOT EXISTS mess_waste_logs (
  log_id INTEGER PRIMARY KEY AUTOINCREMENT,
  mess_id TEXT NOT NULL,                  -- e.g. 'Mess 1' (= bins.group_name)
  date TEXT NOT NULL,
  meal TEXT NOT NULL CHECK (meal IN ('breakfast','lunch','snacks','dinner')),
  category TEXT NOT NULL CHECK (category IN ('plate','kitchen_prep','unserved')),
  weight_kg REAL NOT NULL CHECK (weight_kg > 0 AND weight_kg <= 500),
  weighed INTEGER NOT NULL CHECK (weighed IN (0,1)),
  logged_by TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('simulated','staff')),
  created_at TEXT NOT NULL);
"""


def get_conn(db_path=None) -> sqlite3.Connection:
    """Open a connection to db_path (default config.DB_PATH), creating its folder."""
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI may open the connection (dependency) and
    # use it (endpoint) on different threadpool threads within one request.
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(reset: bool = False, db_path=None) -> None:
    """Create all tables. reset=True deletes the database file (and its WAL files) first."""
    path = Path(db_path or config.DB_PATH)
    if reset:
        for suffix in ("", "-wal", "-shm"):
            Path(str(path) + suffix).unlink(missing_ok=True)
    conn = get_conn(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_db():
    """FastAPI dependency: one connection per request, closed afterwards."""
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


def get_meta(conn, key) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn, key, value) -> None:
    """Insert or replace one meta value (stored as text) and commit."""
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)))
    conn.commit()


def now_iso() -> str:
    """Current time as an ISO 8601 string in UTC+05:30."""
    return datetime.now(config.TZ).isoformat(timespec="seconds")
