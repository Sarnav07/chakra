"""Seed the synthetic campus, observations and mess logs."""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta

import numpy as np

from app import config
from app.db import get_conn, init_db, now_iso
from app.sim import scenario
from app.sim.simulator import build_layout, draw_days, history_policy_b, run_days


def run_seed(
    seed: int = 42, scenario_date: date | None = None, db_path=None,
) -> dict:
    """Rebuild the demo database with 45 deterministic history days."""
    scenario_date = scenario_date or datetime.now(config.TZ).date()
    init_db(reset=True, db_path=db_path)
    layout = build_layout(seed)
    start_date = scenario_date - timedelta(days=scenario.HISTORY_DAYS - 1)
    draws = draw_days(layout, start_date, scenario.HISTORY_DAYS, seed, scenario_date)

    rng = np.random.default_rng(seed)
    stale_ids = sorted(
        rng.choice([row['bin_id'] for row in layout], size=scenario.STALE_DEMO_BIN_COUNT, replace=False).tolist()
    )
    for draw in draws[-2:]:
        for bin_id in draw['missing_reading']:
            draw['missing_reading'][bin_id] = bin_id in stale_ids

    result = run_days(layout, draws, history_policy_b)
    conn = get_conn(db_path)
    try:
        created_at = now_iso()
        plan_date = scenario_date + timedelta(days=1)
        scenario_now = datetime.combine(scenario_date, time(20, 30), tzinfo=config.TZ)
        metadata = {
            'scenario_date': scenario_date.isoformat(),
            'plan_date': plan_date.isoformat(),
            'scenario_now': scenario_now.isoformat(timespec='seconds'),
            'seed': seed,
            'created_at': created_at,
            'data_label': 'simulated',
        }
        conn.executemany('INSERT INTO meta(key,value) VALUES (?,?)', metadata.items())
        conn.executemany(
            'INSERT INTO bins(bin_id,name,group_type,group_name,stream,lat,lon,capacity_l) '
            'VALUES (:bin_id,:name,:group_type,:group_name,:stream,:lat,:lon,:capacity_l)',
            layout,
        )
        conn.executemany(
            'INSERT INTO nodes(node_id,name,kind,lat,lon) VALUES (:node_id,:name,:kind,:lat,:lon)',
            config.NODES,
        )
        conn.executemany(
            'INSERT INTO vehicles(vehicle_id,capacity_l,fixed_cost_rs,cost_per_km_rs) '
            'VALUES (:vehicle_id,:capacity_l,:fixed_cost_rs,:cost_per_km_rs)',
            config.VEHICLES,
        )

        observation_times = {
            (draw['date'], bin_id): f"{draw['date']}T20:00:00+05:30"
            for draw in draws for bin_id in layout_by_id(layout)
        }
        conn.executemany(
            'INSERT INTO fill_observations(bin_id,observed_at,fill_pct,source) '
            'VALUES (?,?,?,?)',
            [
                (
                    row['bin_id'], observation_times[(row['date'], row['bin_id'])],
                    row['fill_pct'], 'simulated',
                )
                for row in result['observations']
            ],
        )
        conn.executemany(
            'INSERT INTO pickup_events(route_id,bin_id,completed_at,collected_volume_l,level) '
            'VALUES (?,?,?,?,NULL)',
            [
                (
                    f"HIST-{row['date']}", row['bin_id'], f"{row['date']}T09:00:00+05:30",
                    row['collected_volume_l'],
                )
                for row in result['pickups']
            ],
        )
        conn.executemany(
            'INSERT INTO mess_waste_logs(mess_id,date,meal,category,weight_kg,weighed,logged_by,source,created_at) '
            'VALUES (:mess_id,:date,:meal,:category,:weight_kg,:weighed,:logged_by,:source,:created_at)',
            result['meal_logs'],
        )
        conn.commit()
        summary = {
            'bins': len(layout),
            'observations': len(result['observations']),
            'history_pickups': len(result['pickups']),
            'mess_waste_logs': len(result['meal_logs']),
            'stale_demo_bins': stale_ids,
            'scenario_date': scenario_date.isoformat(),
            'plan_date': plan_date.isoformat(),
        }
        return summary
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def layout_by_id(layout: list[dict]) -> list[str]:
    return [row['bin_id'] for row in layout]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--date', type=date.fromisoformat)
    parser.add_argument('--with-twin', action='store_true')
    parser.add_argument('--with-scale', action='store_true')
    args = parser.parse_args()
    print('Seed summary:', run_seed(args.seed, args.date))
    if args.with_twin:
        try:
            from app.twin.policies import run_twin

            print('Twin:', run_twin())
        except NotImplementedError:
            print('skipped: not built yet')
    if args.with_scale:
        try:
            from app.scale_lab.run import run_scale_lab

            print('Scale lab:', run_scale_lab())
        except NotImplementedError:
            print('skipped: not built yet')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
