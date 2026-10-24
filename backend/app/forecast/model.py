"""Quantile fill forecasts from observation, pickup and mess-log history."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd

from app import config
from app.db import get_meta
from app.selection.select import p_overflow_from_quantiles

FEATURE_COLUMNS = (
    'group_hostel', 'group_mess', 'group_department', 'group_mess_food',
    'weekday', 'is_weekend', 'exam_week', 'capacity_l',
    'mean_last_7_increments', 'last_increment', 'mess_kg_previous_day',
)
_ALPHAS = (0.1, 0.5, 0.9)
_MODEL_CACHE: dict[tuple, tuple[dict, pd.DataFrame]] = {}


def frames_from_db(conn) -> dict[str, pd.DataFrame]:
    """Return the four source tables as independent pandas frames."""
    return {
        'bins': pd.read_sql_query('SELECT * FROM bins ORDER BY bin_id', conn),
        'observations': pd.read_sql_query(
            'SELECT * FROM fill_observations ORDER BY obs_id', conn
        ),
        'pickups': pd.read_sql_query(
            'SELECT * FROM pickup_events ORDER BY pickup_id', conn
        ),
        'mess_logs': pd.read_sql_query(
            'SELECT * FROM mess_waste_logs ORDER BY log_id', conn
        ),
    }


def _timestamp(value) -> datetime:
    return datetime.fromisoformat(str(value))


def build_increments(observations: pd.DataFrame, pickups: pd.DataFrame) -> pd.DataFrame:
    """Calculate valid increments between adjacent observed calendar days."""
    columns = ['bin_id', 'target_date', 'increment_pct', 'last_increment']
    if observations.empty:
        return pd.DataFrame(columns=columns)
    all_obs = observations.copy()
    all_obs['_at'] = all_obs['observed_at'].map(_timestamp)
    reset_rows = all_obs[all_obs['source'] == 'pickup_reset']
    measured = all_obs[all_obs['source'].isin(('simulated', 'staff_tap', 'camera'))]
    measured['_date'] = measured['_at'].map(lambda stamp: stamp.date())
    measured = measured.sort_values('obs_id').drop_duplicates(['bin_id', '_date'], keep='last')

    pickup_rows = pickups.copy()
    if not pickup_rows.empty:
        pickup_rows['_at'] = pickup_rows['completed_at'].map(_timestamp)
    increments = []
    for bin_id, rows in measured.groupby('bin_id', sort=True):
        rows = rows.sort_values('_date')
        previous = None
        for current in rows.to_dict('records'):
            if previous is not None and (current['_date'] - previous['_date']).days == 1:
                start_at, end_at = previous['_at'], current['_at']
                had_pickup = False
                if not pickup_rows.empty:
                    between = pickup_rows[
                        (pickup_rows['bin_id'] == bin_id)
                        & (pickup_rows['_at'] > start_at)
                        & (pickup_rows['_at'] <= end_at)
                    ]
                    had_pickup = not between.empty
                if not reset_rows.empty:
                    between_reset = reset_rows[
                        (reset_rows['bin_id'] == bin_id)
                        & (reset_rows['_at'] > start_at)
                        & (reset_rows['_at'] <= end_at)
                    ]
                    had_pickup = had_pickup or not between_reset.empty
                old_fill, new_fill = float(previous['fill_pct']), float(current['fill_pct'])
                if old_fill != 100.0 and new_fill != 100.0:
                    increments.append(
                        {
                            'bin_id': bin_id,
                            'target_date': current['_date'],
                            'increment_pct': new_fill if had_pickup else new_fill - old_fill,
                        }
                    )
            previous = current
    result = pd.DataFrame(increments)
    if result.empty:
        return pd.DataFrame(columns=columns)
    result = result.sort_values(['bin_id', 'target_date']).reset_index(drop=True)
    result['last_increment'] = result.groupby('bin_id')['increment_pct'].shift(1)
    return result


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _exam_week(target_date: date, scenario_date: date) -> int:
    return int(
        scenario_date - timedelta(days=28) <= target_date < scenario_date - timedelta(days=21)
        or scenario_date + timedelta(days=14) <= target_date < scenario_date + timedelta(days=21)
    )


def build_features(
    bins: pd.DataFrame,
    increments: pd.DataFrame,
    target_pairs,
    mess_logs: pd.DataFrame | None = None,
    scenario_date: date | None = None,
) -> pd.DataFrame:
    """Build causal feature rows for (bin_id, target_date) pairs."""
    target_pairs = list(target_pairs)
    bin_lookup = bins.set_index('bin_id').to_dict('index')
    increments_by_bin = {
        key: group.sort_values('target_date')
        for key, group in increments.groupby('bin_id', sort=False)
    } if not increments.empty else {}
    if mess_logs is None:
        mess_logs = pd.DataFrame(columns=['mess_id', 'date', 'weight_kg'])
    log_totals = {}
    if not mess_logs.empty:
        for row in mess_logs.to_dict('records'):
            log_totals[(row['mess_id'], _as_date(row['date']))] = (
                log_totals.get((row['mess_id'], _as_date(row['date'])), 0.0)
                + float(row['weight_kg'])
            )
    scenario_date = scenario_date or max(
        (_as_date(pair[1] if not isinstance(pair, dict) else pair['target_date']) for pair in target_pairs),
        default=date.today(),
    )
    output = []
    for pair in target_pairs:
        if isinstance(pair, dict):
            bin_id, target_date = pair['bin_id'], _as_date(pair['target_date'])
        else:
            bin_id, target_date = pair[0], _as_date(pair[1])
        row = bin_lookup[bin_id]
        prior = increments_by_bin.get(bin_id)
        if prior is not None:
            prior = prior[prior['target_date'].map(_as_date) < target_date]
        values = prior['increment_pct'].astype(float).tolist()[-7:] if prior is not None else []
        last_increment = values[-1] if values else 0.0
        group = row['group_type']
        mess_id = row['group_name'] if group == 'mess_food' else None
        food_kg = log_totals.get((mess_id, target_date - timedelta(days=1)), 0.0) if mess_id else 0.0
        output.append(
            {
                'group_hostel': int(group == 'hostel'),
                'group_mess': int(group == 'mess'),
                'group_department': int(group == 'department'),
                'group_mess_food': int(group == 'mess_food'),
                'weekday': target_date.weekday(),
                'is_weekend': int(target_date.weekday() >= 5),
                'exam_week': _exam_week(target_date, scenario_date),
                'capacity_l': float(row['capacity_l']),
                'mean_last_7_increments': sum(values) / len(values) if values else 0.0,
                'last_increment': last_increment,
                'mess_kg_previous_day': food_kg,
            }
        )
    return pd.DataFrame(output, columns=FEATURE_COLUMNS)


def train_quantile_models(train_rows: pd.DataFrame) -> dict[float, object]:
    """Fit the three fixed gradient-boosted quantile models."""
    from sklearn.ensemble import GradientBoostingRegressor

    if train_rows.empty:
        raise ValueError('No training increments are available')
    x = train_rows.loc[:, FEATURE_COLUMNS]
    y = train_rows['increment_pct'].astype(float)
    return {
        alpha: GradientBoostingRegressor(
            loss='quantile', alpha=alpha, n_estimators=200, max_depth=3,
            learning_rate=0.05, random_state=0,
        ).fit(x, y)
        for alpha in _ALPHAS
    }


def predict_quantiles(models: dict[float, object], feature_rows: pd.DataFrame):
    """Return ordered, nonnegative p10/p50/p90 predictions as float lists."""
    import numpy as np

    if feature_rows.empty:
        return [], [], []
    predictions = np.vstack([models[alpha].predict(feature_rows.loc[:, FEATURE_COLUMNS]) for alpha in _ALPHAS]).T
    predictions = np.maximum(predictions, 0.0)
    predictions.sort(axis=1)
    return tuple(predictions[:, index].astype(float).tolist() for index in range(3))


def _history(conn):
    frames = frames_from_db(conn)
    increments = build_increments(frames['observations'], frames['pickups'])
    scenario_date_value = get_meta(conn, 'scenario_date')
    if scenario_date_value is None:
        raise ValueError('Database not seeded - run python -m app.seed')
    scenario_date = date.fromisoformat(scenario_date_value)
    return frames, increments, scenario_date


def evaluate(conn) -> dict:
    """Evaluate quantiles on the last ten increment dates, without random shuffling."""
    from sklearn.metrics import mean_absolute_error

    frames, increments, scenario_date = _history(conn)
    if increments.empty:
        raise ValueError('No valid increment pairs are available for forecast evaluation')
    latest = max(_as_date(value) for value in increments['target_date'])
    cutoff = latest - timedelta(days=9)
    train = increments[increments['target_date'].map(_as_date) < cutoff].copy()
    valid = increments[increments['target_date'].map(_as_date) >= cutoff].copy()
    if train.empty or valid.empty:
        raise ValueError('At least one training day and one validation day are required')
    train_features = build_features(
        frames['bins'], increments, list(zip(train['bin_id'], train['target_date'])),
        frames['mess_logs'], scenario_date,
    )
    valid_features = build_features(
        frames['bins'], increments, list(zip(valid['bin_id'], valid['target_date'])),
        frames['mess_logs'], scenario_date,
    )
    models = train_quantile_models(train_features.assign(increment_pct=train['increment_pct'].to_numpy()))
    p10, p50, p90 = predict_quantiles(models, valid_features)
    actual = valid['increment_pct'].astype(float).tolist()
    baseline = valid_features['last_increment'].astype(float).tolist()
    return {
        'model_version': 'gbq-v1-' + scenario_date.isoformat(),
        'train_days': len({_as_date(value) for value in train['target_date']}),
        'val_days': len({_as_date(value) for value in valid['target_date']}),
        'mae_model': float(mean_absolute_error(actual, p50)),
        'mae_baseline': float(mean_absolute_error(actual, baseline)),
        'interval_coverage': float(sum(lo <= y <= hi for lo, y, hi in zip(p10, actual, p90)) / len(actual)),
        'n_val': len(actual),
    }


def _cache_key(conn) -> tuple:
    database_path = conn.execute('PRAGMA database_list').fetchone()[2] or ':memory:'
    source_heads = tuple(
        conn.execute(f'SELECT COALESCE(MAX({id_column}), 0) FROM {table}').fetchone()[0]
        for table, id_column in (
            ('fill_observations', 'obs_id'), ('pickup_events', 'pickup_id'),
            ('mess_waste_logs', 'log_id'),
        )
    )
    return database_path, get_meta(conn, 'created_at') or '', source_heads


def _get_full_models(conn, frames, increments, scenario_date):
    key = _cache_key(conn)
    cached = _MODEL_CACHE.get(key)
    if cached is not None:
        return cached[0]
    pairs = list(zip(increments['bin_id'], increments['target_date']))
    features = build_features(frames['bins'], increments, pairs, frames['mess_logs'], scenario_date)
    training = features.copy()
    training['increment_pct'] = increments['increment_pct'].astype(float).to_numpy()
    models = train_quantile_models(training)
    _MODEL_CACHE.clear()
    _MODEL_CACHE[key] = (models, increments)
    return models


def forecast_bins(conn, plan_date: date) -> list[dict]:
    """Forecast each bin through the end of plan_date without storing rows."""
    frames, increments, scenario_date = _history(conn)
    if increments.empty:
        raise ValueError('No valid increment pairs are available for forecasting')
    models = _get_full_models(conn, frames, increments, scenario_date)
    latest = (
        frames['observations'].sort_values('obs_id').drop_duplicates('bin_id', keep='last')
        .set_index('bin_id')
    )
    target_pairs = [(bin_id, plan_date) for bin_id in frames['bins']['bin_id']]
    features = build_features(frames['bins'], increments, target_pairs, frames['mess_logs'], scenario_date)
    p10, p50, p90 = predict_quantiles(models, features)
    horizon_end = datetime.combine(plan_date, time(23, 59, 59), tzinfo=config.TZ).isoformat(timespec='seconds')
    model_version = 'gbq-v1-' + scenario_date.isoformat()
    result = []
    for index, bin_id in enumerate(frames['bins']['bin_id']):
        observation = latest.loc[bin_id] if bin_id in latest.index else None
        current = float(observation['fill_pct']) if observation is not None else None
        if current is None:
            inc10 = inc50 = inc90 = predicted = low = high = probability = None
        else:
            inc10, inc50, inc90 = p10[index], p50[index], p90[index]
            predicted = current + inc50
            low, high = current + inc10, current + inc90
            probability = p_overflow_from_quantiles(current, inc10, inc50, inc90)
        result.append(
            {
                'bin_id': bin_id,
                'current_fill_pct': current,
                'predicted_increment_pct': inc50,
                'predicted_fill_pct': predicted,
                'p10_fill_pct': low,
                'p90_fill_pct': high,
                'p_overflow': probability,
                'plan_date': plan_date.isoformat(),
                'horizon_end': horizon_end,
                'model_version': model_version,
            }
        )
    return result


def persist_forecasts(conn, forecasts: list[dict]) -> list[dict]:
    """Insert one forecast set and return each row with its forecast_id."""
    created_at = datetime.now(config.TZ).isoformat(timespec='microseconds')
    output = []
    for forecast in forecasts:
        cursor = conn.execute(
            'INSERT INTO fill_forecasts(bin_id,created_at,plan_date,horizon_end,current_fill_pct,'
            'predicted_increment_pct,predicted_fill_pct,p10_fill_pct,p90_fill_pct,p_overflow,model_version) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (
                forecast['bin_id'], created_at, forecast['plan_date'], forecast['horizon_end'],
                forecast['current_fill_pct'], forecast['predicted_increment_pct'],
                forecast['predicted_fill_pct'], forecast['p10_fill_pct'], forecast['p90_fill_pct'],
                forecast['p_overflow'], forecast['model_version'],
            ),
        )
        output.append({'forecast_id': cursor.lastrowid, **forecast})
    conn.commit()
    return output
