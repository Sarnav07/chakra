"""P1 common-random-number twin checks."""

from app import config
from app.twin.policies import load_twin_cache, run_twin


def test_three_day_twin_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEMO_CACHE_DIR", tmp_path)
    first = run_twin(seeds=(11,), days=3)
    second = run_twin(seeds=(11,), days=3)
    assert first["days"] == 3
    assert first["seeds"] == [11]
    assert first["synthetic"] is True
    assert {row["policy"] for row in first["policies"]} == {
        "A_fixed", "B_rule70", "C_chakra",
    }
    assert [row["tau"] for row in first["sweep"]] == [round(i / 10, 1) for i in range(1, 10)]
    fixed_pickups = next(row for row in first["policies"] if row["policy"] == "A_fixed")["mean"]["pickups"]
    assert 0 < fixed_pickups <= 150
    assert all(row["mean"]["overflow_events"] >= 0 for row in first["policies"])
    assert first["policies"] == second["policies"]
    assert first["sweep"] == second["sweep"]
    assert first["sensitivity"] == second["sensitivity"]
    assert load_twin_cache() == second
