"""Deterministic scenario generation and daily fill simulation."""

from __future__ import annotations

import csv
import warnings
from collections.abc import Callable, Mapping
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from app import config
from app.sim import scenario


def build_layout(seed: int = 42) -> list[dict]:
    """Build the 50-bin synthetic campus and apply an optional position file."""
    rng = np.random.default_rng(seed)
    layout = []
    group_centres: dict[tuple[str, str], tuple[float, float]] = {}
    for group_type, group_name, count, capacity_l in scenario.GROUPS:
        key = (group_type, group_name)
        if key not in group_centres:
            group_centres[key] = (
                float(rng.uniform(config.CAMPUS_CENTER[0] - 0.006, config.CAMPUS_CENTER[0] + 0.006)),
                float(rng.uniform(config.CAMPUS_CENTER[1] - 0.007, config.CAMPUS_CENTER[1] + 0.007)),
            )
        centre = group_centres[key]
        for index in range(1, count + 1):
            if group_type == 'hostel':
                letter = group_name[-1]
                bin_id = f'H{letter}-{index}'
                name = f'{group_name} bin {index}'
            elif group_type == 'mess':
                mess_number = group_name.split()[-1]
                bin_id = f'M{mess_number}-G{index}'
                name = f'{group_name} general bin {index}'
            elif group_type == 'mess_food':
                mess_number = group_name.split()[-1]
                bin_id = f'M{mess_number}-F{index}'
                name = f'{group_name} food bin {index}'
            else:
                department_number = group_name.split()[-1]
                bin_id = f'D{department_number}-{index}'
                name = f'{group_name} bin {index}'
            layout.append(
                {
                    'bin_id': bin_id,
                    'name': name,
                    'group_type': group_type,
                    'group_name': group_name,
                    'stream': 'food' if group_type == 'mess_food' else 'general',
                    'lat': centre[0] + float(rng.uniform(-0.0005, 0.0005)),
                    'lon': centre[1] + float(rng.uniform(-0.0005, 0.0005)),
                    'capacity_l': capacity_l,
                }
            )
    _apply_real_positions(layout)
    return layout


def _apply_real_positions(layout: list[dict]) -> None:
    path = config.DATA_DIR / 'real_bins.csv'
    if not path.is_file():
        return
    by_id = {row['bin_id']: row for row in layout}
    unknown = []
    with path.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        required = {'bin_id', 'name', 'lat', 'lon'}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f'{path} must contain columns {sorted(required)}')
        for row in reader:
            bin_id = row['bin_id'].strip()
            if bin_id not in by_id:
                unknown.append(bin_id)
                continue
            by_id[bin_id].update(
                name=row['name'].strip() or by_id[bin_id]['name'],
                lat=float(row['lat']),
                lon=float(row['lon']),
            )
    if unknown:
        warnings.warn(f'Ignoring unknown bin IDs in {path}: {", ".join(unknown)}', stacklevel=2)


def _is_exam_day(day: date, scenario_date: date) -> bool:
    return scenario_date - timedelta(days=28) <= day < scenario_date - timedelta(days=21) or (
        scenario_date + timedelta(days=14) <= day < scenario_date + timedelta(days=21)
    )


def draw_days(
    layout: list[dict], start_date: date, n_days: int, seed: int,
    scenario_date: date | None = None,
) -> list[dict]:
    """Pre-draw increments, meal logs and observation missingness for reuse by policies."""
    if n_days < 0:
        raise ValueError('n_days must be nonnegative')
    scenario_date = scenario_date or (start_date + timedelta(days=n_days - 1))
    rng = np.random.default_rng(seed)
    multipliers = {
        row['bin_id']: float(rng.uniform(*scenario.BIN_MULTIPLIER_RANGE))
        for row in layout if row['stream'] == 'general'
    }
    mess_ids = sorted({row['group_name'] for row in layout if row['group_type'] == 'mess_food'})
    output = []
    for offset in range(n_days):
        current_date = start_date + timedelta(days=offset)
        general_increment = {}
        for row in layout:
            if row['stream'] != 'general':
                continue
            group = row['group_type']
            mean = scenario.BASE_RATE_PCT[group]
            mean *= scenario.WEEKDAY_FACTOR[group][current_date.weekday()]
            if _is_exam_day(current_date, scenario_date):
                mean *= scenario.EXAM_FACTOR[group]
            noise = float(rng.lognormal(mean=0.0, sigma=scenario.INCREMENT_LOG_SIGMA))
            general_increment[row['bin_id']] = mean * multipliers[row['bin_id']] * noise

        meal_logs = []
        food_increment = {
            row['bin_id']: 0.0 for row in layout if row['stream'] == 'food'
        }
        for mess_id in mess_ids:
            mess_multiplier = float(rng.uniform(*scenario.MESS_MULTIPLIER_RANGE))
            bins = [row for row in layout if row['group_type'] == 'mess_food' and row['group_name'] == mess_id]
            for meal, base_kg in scenario.MEAL_BASE_KG.items():
                total_kg = base_kg * mess_multiplier * float(
                    rng.lognormal(mean=0.0, sigma=scenario.FOOD_LOG_SIGMA)
                )
                for category, share in scenario.MEAL_CATEGORY_SHARES.items():
                    weight_kg = round(total_kg * share, 1)
                    meal_logs.append(
                        {
                            'mess_id': mess_id,
                            'date': current_date.isoformat(),
                            'meal': meal,
                            'category': category,
                            'weight_kg': weight_kg,
                            'weighed': int(rng.random() < scenario.WEIGHED_PROBABILITY),
                            'logged_by': 'simulated',
                            'source': 'simulated',
                            'created_at': f'{current_date.isoformat()}T20:00:00+05:30',
                        }
                    )
                    food_l = weight_kg / config.FOOD_DENSITY_KG_PER_L
                    for row in bins:
                        food_increment[row['bin_id']] += (
                            food_l / len(bins) / row['capacity_l'] * 100.0
                        )

        output.append(
            {
                'date': current_date.isoformat(),
                'general_increment': general_increment,
                'food_increment': food_increment,
                'meal_logs': meal_logs,
                'observation_noise': {
                    row['bin_id']: float(rng.normal(0.0, scenario.OBSERVATION_NOISE_SIGMA))
                    for row in layout
                },
                'missing_reading': {
                    row['bin_id']: bool(rng.random() < scenario.MISSING_PROBABILITY)
                    for row in layout
                },
            }
        )
    return output


def history_policy_b(
    day_index: int, current_date: str, last_observations: Mapping[str, float],
    stale_flags: Mapping[str, int],
) -> set[str]:
    del day_index, current_date
    return {bin_id for bin_id, fill in last_observations.items() if fill > 70.0} | {
        bin_id for bin_id, missing_days in stale_flags.items() if missing_days >= 2
    }


def run_days(
    layout: list[dict], draws: list[dict],
    policy: Callable[[int, str, Mapping[str, float], Mapping[str, int]], set[str]],
    start_true_fill: Mapping[str, float] | None = None,
    start_observations: Mapping[str, float] | None = None,
    start_missing_days: Mapping[str, int] | None = None,
    on_day_complete: Callable[[str, list[dict], list[dict], list[dict]], None] | None = None,
) -> dict:
    """Apply 09:00 pickups, daily growth and clipped 20:00 readings."""
    ids = {row['bin_id'] for row in layout}
    capacities = {row['bin_id']: row['capacity_l'] for row in layout}
    true_fill = {bin_id: float((start_true_fill or {}).get(bin_id, 0.0)) for bin_id in ids}
    last_observations: dict[str, float] = dict(start_observations or {})
    missing_days = {bin_id: int((start_missing_days or {}).get(bin_id, 0)) for bin_id in ids}
    observations, pickups, overflows = [], [], []
    for day_index, draw in enumerate(draws):
        current_date = draw['date']
        pickup_start = len(pickups)
        observation_start = len(observations)
        selected = set(policy(day_index, current_date, dict(last_observations), dict(missing_days)))
        unknown = selected - ids
        if unknown:
            raise ValueError(f'Policy selected unknown bins: {sorted(unknown)}')
        for bin_id in sorted(selected):
            fill_before = true_fill[bin_id]
            pickups.append(
                {
                    'date': current_date,
                    'bin_id': bin_id,
                    'fill_before_pct': fill_before,
                    'collected_volume_l': min(fill_before, 100.0) * capacities[bin_id] / 100.0,
                }
            )
            true_fill[bin_id] = 0.0
        for bin_id in sorted(ids):
            increment = draw['general_increment'].get(bin_id, 0.0) + draw['food_increment'].get(bin_id, 0.0)
            true_fill[bin_id] = min(scenario.TRUE_FILL_CAP, max(0.0, true_fill[bin_id] + increment))
            if true_fill[bin_id] >= 100.0:
                overflows.append({'date': current_date, 'bin_id': bin_id})
            if draw['missing_reading'][bin_id]:
                missing_days[bin_id] += 1
                continue
            observed = min(
                100.0,
                max(0.0, round(true_fill[bin_id] + draw['observation_noise'][bin_id])),
            )
            observations.append(
                {'date': current_date, 'bin_id': bin_id, 'fill_pct': observed, 'source': 'simulated'}
            )
            last_observations[bin_id] = observed
            missing_days[bin_id] = 0
        if on_day_complete is not None:
            on_day_complete(
                current_date, observations[observation_start:], pickups[pickup_start:],
                draw['meal_logs'],
            )
    return {
        'observations': observations,
        'pickups': pickups,
        'overflow_events': overflows,
        'meal_logs': [row for draw in draws for row in draw['meal_logs']],
        'final_true_fill': true_fill,
        'last_observations': last_observations,
        'missing_days': missing_days,
    }
