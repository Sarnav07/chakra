"""P1 forecast data and API checks."""

import pandas as pd

from app.db import get_conn
from app.forecast.model import build_increments, evaluate


def test_increments_handle_pickup_and_censored_reading():
    observations = pd.DataFrame([
        {"obs_id": i, "bin_id": "HA-1", "observed_at": f"2026-10-0{i}T20:00:00+05:30",
         "fill_pct": fill, "source": "simulated"}
        for i, fill in enumerate((20, 30, 40, 100), start=1)
    ])
    pickups = pd.DataFrame([
        {"bin_id": "HA-1", "completed_at": "2026-10-03T09:00:00+05:30"}
    ])
    rows = build_increments(observations, pickups)
    assert rows["increment_pct"].tolist() == [10.0, 40.0]
    assert [str(value) for value in rows["target_date"]] == ["2026-10-02", "2026-10-03"]


def test_forecast_evaluation_and_api(seeded_db_path, seeded_client):
    conn = get_conn(seeded_db_path)
    try:
        metrics = evaluate(conn)
    finally:
        conn.close()
    assert metrics["n_val"] > 0
    assert metrics["mae_model"] >= 0
    assert metrics["mae_baseline"] >= 0
    assert 0 <= metrics["interval_coverage"] <= 1
    print("P1 forecast evaluation:", metrics)

    response = seeded_client.post("/api/forecasts", json={})
    assert response.status_code == 200, response.text
    forecasts = response.json()["forecasts"]
    assert len(forecasts) == 50
    assert all(0 <= row["p_overflow"] <= 1 for row in forecasts if row["p_overflow"] is not None)
    latest = seeded_client.get("/api/forecasts/latest")
    assert latest.status_code == 200
    assert len(latest.json()["forecasts"]) == 50


def test_observation_updates_latest_fill(seeded_client):
    response = seeded_client.post("/api/observations", json={"bin_id": "HA-1", "level": "full"})
    assert response.status_code == 200, response.text
    assert response.json()["observation"]["fill_pct"] == 90
    bins = seeded_client.get("/api/bins").json()["bins"]
    assert next(row for row in bins if row["bin_id"] == "HA-1")["latest_fill_pct"] == 90
    assert seeded_client.post("/api/observations", json={
        "bin_id": "HA-1", "level": "low", "fill_pct": 20,
    }).status_code == 422


def test_forecast_eval_requires_seeded_database(client):
    response = client.get("/api/forecasts/eval")
    assert response.status_code == 422
    assert response.json()["detail"] == "Database not seeded - run python -m app.seed"
