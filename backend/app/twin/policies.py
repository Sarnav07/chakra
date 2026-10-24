"""Thirty-day synthetic comparison of collection selection policies."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from pathlib import Path

from app import config
from app.forecast.model import (
    build_features, build_increments, predict_quantiles, train_quantile_models,
)
from app.routing.plan import plan_routes
from app.routing.types import RoutingSettings, Stop
from app.selection.select import classify_bin, p_overflow_from_quantiles
from app.sim import scenario
from app.sim.simulator import build_layout, draw_days, history_policy_b, run_days

METRICS = ("km", "route_minutes", "cost_rs", "overflow_events", "pickups")
SWEEP = tuple(round(index / 10, 1) for index in range(1, 10))


def _run_policy(layout, draws, warmup, choose, route_planner):
    daily_routes = []
    all_ids = {row["bin_id"] for row in layout}

    def policy(day_index, current_date, last_observations, stale_flags):
        requested = set(choose(day_index, current_date, last_observations, stale_flags))
        if requested - all_ids:
            raise ValueError(f"Policy requested unknown bins: {sorted(requested - all_ids)}")
        route = route_planner(requested, last_observations)
        served = set(route["served_bin_ids"])
        if served - requested:
            raise ValueError("Router served a bin that was not selected")
        daily_routes.append(route)
        return served

    simulation = run_days(
        layout, draws, policy, warmup["final_true_fill"],
        warmup["last_observations"], warmup["missing_days"],
        on_day_complete=getattr(choose, "observe_day", None),
    )
    return {
        "km": sum(day["km"] for day in daily_routes),
        "route_minutes": sum(day["route_minutes"] for day in daily_routes),
        "cost_rs": sum(day["cost_rs"] for day in daily_routes),
        "overflow_events": len(simulation["overflow_events"]),
        "pickups": len(simulation["pickups"]),
        "bin_days": len(layout) * len(draws),
    }


def compare_policies(layout, draws, warmup, risk_tracker_factory, route_planner,
                     default_tau=config.DEFAULT_TAU, sweep=SWEEP):
    """Run each policy from one warm-up state with common daily draws."""
    all_ids = {row["bin_id"] for row in layout}

    def risk_choice(tau):
        tracker = risk_tracker_factory()
        def choose(day_index, current_date, last_observations, stale_flags):
            risks = tracker.predict(current_date, last_observations)
            selected = set()
            for bin_id in all_ids:
                take, _ = classify_bin(
                    last_observations.get(bin_id), risks.get(bin_id),
                    stale_flags.get(bin_id, 0) >= 2, False, tau,
                )
                if take:
                    selected.add(bin_id)
            return selected
        choose.observe_day = tracker.observe_day
        return choose

    results = {
        "A": _run_policy(layout, draws, warmup, lambda *_: all_ids, route_planner),
        "B": _run_policy(layout, draws, warmup, history_policy_b, route_planner),
        "C": _run_policy(layout, draws, warmup, risk_choice(default_tau), route_planner),
        "sweep": {},
    }
    for tau in sweep:
        results["sweep"][tau] = _run_policy(
            layout, draws, warmup, risk_choice(tau), route_planner
        )
    return results


def _warmup_model(layout, warmup, scenario_date):
    """Train on warm-up observations and pickup resets only."""
    import pandas as pd

    observations = pd.DataFrame([
        {
            "obs_id": index, "bin_id": row["bin_id"], "source": "simulated",
            "observed_at": f"{row['date']}T20:00:00+05:30", "fill_pct": row["fill_pct"],
        }
        for index, row in enumerate(warmup["observations"], start=1)
    ])
    pickups = pd.DataFrame([
        {"bin_id": row["bin_id"], "completed_at": f"{row['date']}T09:00:00+05:30"}
        for row in warmup["pickups"]
    ], columns=["bin_id", "completed_at"])
    increments = build_increments(observations, pickups)
    if increments.empty:
        raise ValueError("Twin warm-up produced no valid forecast increments")
    bins = pd.DataFrame(layout)
    logs = pd.DataFrame(warmup["meal_logs"])
    pairs = list(zip(increments["bin_id"], increments["target_date"]))
    features = build_features(bins, increments, pairs, logs, scenario_date)
    training = features.copy()
    training["increment_pct"] = increments["increment_pct"].to_numpy()
    models = train_quantile_models(training)
    return models, bins, increments, logs


def _risk_predictor(layout, models, bins, increments, logs, warmup, scenario_date):
    import pandas as pd

    ids = [row["bin_id"] for row in layout]
    prior = {
        row["bin_id"]: row for row in warmup["observations"]
    }

    class RiskTracker:
        def __init__(self):
            self.increments = increments.copy()
            self.logs = logs.copy()
            self.prior = prior.copy()

        def predict(self, current_date, last_observations):
            target_date = datetime.fromisoformat(current_date).date()
            features = build_features(
                bins, self.increments, [(bin_id, target_date) for bin_id in ids],
                self.logs, scenario_date,
            )
            p10, p50, p90 = predict_quantiles(models, features)
            return {
                bin_id: p_overflow_from_quantiles(
                    last_observations.get(bin_id), p10[index], p50[index], p90[index]
                )
                for index, bin_id in enumerate(ids)
            }

        def observe_day(self, current_date, observations, pickups, meal_logs):
            picked = {row["bin_id"] for row in pickups}
            new_increments = []
            for row in observations:
                bin_id = row["bin_id"]
                previous = self.prior.get(bin_id)
                if previous is not None and (
                    datetime.fromisoformat(current_date).date()
                    - datetime.fromisoformat(previous["date"]).date()
                ).days == 1:
                    old, new = float(previous["fill_pct"]), float(row["fill_pct"])
                    if old != 100.0 and new != 100.0:
                        new_increments.append({
                            "bin_id": bin_id, "target_date": datetime.fromisoformat(current_date).date(),
                            "increment_pct": new if bin_id in picked else new - old,
                            "last_increment": 0.0,
                        })
                self.prior[bin_id] = row
            if new_increments:
                self.increments = pd.concat(
                    [self.increments, pd.DataFrame(new_increments)], ignore_index=True,
                )
            if meal_logs:
                self.logs = pd.concat([self.logs, pd.DataFrame(meal_logs)], ignore_index=True)

    return RiskTracker


def _route_planner(layout, detour_factor):
    by_id = {row["bin_id"]: row for row in layout}
    settings = RoutingSettings(detour_factor=detour_factor)

    def route(requested, last_observations):
        stops = []
        for bin_id in sorted(requested):
            row = by_id[bin_id]
            reading = last_observations.get(bin_id)
            fill = config.STALE_DEMAND_PCT if reading is None else max(
                float(reading), config.MIN_DEMAND_PCT
            )
            stops.append(Stop(
                bin_id=bin_id, name=row["name"], lat=row["lat"], lon=row["lon"],
                stream=row["stream"], demand_l=row["capacity_l"] * fill / 100.0,
            ))
        planning = plan_routes(stops, fast=True, settings=settings)
        alternatives = planning["alternatives"]
        recommended = planning["recommended_fleet_size"]
        if recommended is None:
            alternative = min(
                alternatives,
                key=lambda item: (len(item["unassigned_bin_ids"]), item["total_cost_rs"]),
            )
        else:
            alternative = next(
                item for item in alternatives if item["fleet_size"] == recommended
            )
        served = {
            bin_id for item in alternative["routes"] for bin_id in item["ordered_bin_ids"]
        }
        if served & set(alternative["unassigned_bin_ids"]):
            raise ValueError("Router put a bin in both a route and the unassigned list")
        return {
            "served_bin_ids": served,
            "km": float(alternative["total_km"]),
            "route_minutes": float(alternative["total_minutes"]),
            "cost_rs": float(alternative["total_cost_rs"]),
        }
    return route


def _aggregate(values):
    return {
        kind: {
            metric: operation(item[metric] for item in values)
            for metric in METRICS
        }
        for kind, operation in (
            ("mean", lambda numbers: sum(numbers) / len(values)),
            ("min", min), ("max", max),
        )
    }


def load_twin_cache() -> dict | None:
    path = Path(config.DEMO_CACHE_DIR) / "twin.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def run_twin(seeds=(11, 22, 33), days=30) -> dict:
    """Run all policies, cache aggregate results, and return them."""
    if not seeds or days < 1:
        raise ValueError("Twin requires at least one seed and one evaluation day")
    scenario_date = datetime.now(config.TZ).date()
    layout = build_layout(config.SEED)
    per_seed = []
    sensitivity = []
    for seed in seeds:
        start = scenario_date - timedelta(days=scenario.HISTORY_DAYS - 1)
        all_draws = draw_days(layout, start, scenario.HISTORY_DAYS + days, seed, scenario_date)
        warm_draws, eval_draws = all_draws[:scenario.HISTORY_DAYS], all_draws[scenario.HISTORY_DAYS:]
        warmup = run_days(layout, warm_draws, history_policy_b)
        models, bins, increments, logs = _warmup_model(layout, warmup, scenario_date)
        predictor = _risk_predictor(layout, models, bins, increments, logs, warmup, scenario_date)
        results = compare_policies(
            layout, eval_draws, warmup, predictor,
            _route_planner(layout, config.DETOUR_FACTOR),
        )
        per_seed.append(results)
        print(f"Twin seed {seed}: completed A, B, C and threshold sweep", flush=True)
        if seed == 11:
            for factor in (1.2, 1.3, 1.5):
                varied = compare_policies(
                    layout, eval_draws, warmup, predictor,
                    _route_planner(layout, factor), sweep=(),
                )
                for key, name in (("A", "A_fixed"), ("C", "C_chakra")):
                    sensitivity.append({
                        "detour_factor": factor, "policy": name,
                        "km": varied[key]["km"],
                        "overflow_events": varied[key]["overflow_events"],
                    })
    policies = []
    for key, name, tau in (
        ("A", "A_fixed", None), ("B", "B_rule70", None),
        ("C", "C_chakra", config.DEFAULT_TAU),
    ):
        policies.append({"policy": name, "tau": tau, **_aggregate([r[key] for r in per_seed])})
    sweep = [
        {"tau": tau, **_aggregate([r["sweep"][tau] for r in per_seed])}
        for tau in SWEEP
    ]
    result = {
        "generated_at": datetime.now(config.TZ).isoformat(timespec="seconds"),
        "synthetic": True,
        "days": days,
        "seeds": list(seeds),
        "policies": policies,
        "sweep": sweep,
        "sensitivity": sensitivity,
        "assumptions": {
            **config.scenario_assumptions(),
            "base_rate_pct": scenario.BASE_RATE_PCT,
            "meal_base_kg": scenario.MEAL_BASE_KG,
            "exam_factor": scenario.EXAM_FACTOR,
        },
    }
    path = Path(config.DEMO_CACHE_DIR) / "twin.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
