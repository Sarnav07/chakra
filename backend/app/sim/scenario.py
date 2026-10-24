"""Synthetic scenario constants from SPEC Section 8."""

GROUPS = [
    *(('hostel', f'Hostel {letter}', 5, 240) for letter in 'ABCDEF'),
    *(('mess', f'Mess {number}', 2, 660) for number in range(1, 4)),
    *(('mess_food', f'Mess {number}', 2, 120) for number in range(1, 4)),
    *(('department', f'Dept {number}', 2, 120) for number in range(1, 5)),
]

BASE_RATE_PCT = {'hostel': 22.0, 'mess': 30.0, 'department': 15.0}
WEEKDAY_FACTOR = {
    'hostel': (1.0, 1.0, 1.0, 1.0, 1.0, 1.15, 1.15),
    'mess': (1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 0.9),
    'department': (1.0, 1.0, 1.0, 1.0, 1.0, 0.4, 0.2),
}
EXAM_FACTOR = {'hostel': 1.25, 'mess': 1.0, 'department': 0.8}
BIN_MULTIPLIER_RANGE = (0.6, 1.4)
INCREMENT_LOG_SIGMA = 0.25
FOOD_LOG_SIGMA = 0.2
OBSERVATION_NOISE_SIGMA = 4.0
TRUE_FILL_CAP = 130.0
MISSING_PROBABILITY = 0.02
STALE_DEMO_BIN_COUNT = 2
HISTORY_DAYS = 45
MEAL_BASE_KG = {'breakfast': 6.0, 'lunch': 14.0, 'snacks': 3.0, 'dinner': 16.0}
MEAL_CATEGORY_SHARES = {'plate': 0.5, 'kitchen_prep': 0.3, 'unserved': 0.2}
MESS_MULTIPLIER_RANGE = (0.8, 1.2)
WEIGHED_PROBABILITY = 0.7
