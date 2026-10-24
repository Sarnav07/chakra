"""Synthetic scenario constants from SPEC Section 8.

Group names are real IIT Roorkee bhawans, messes and departments; centres are
the building positions in OpenStreetMap (ODbL), checked 24 Oct 2026. Bin
positions, fill levels and all history stay simulated.
"""

# (group_type, group_name, bin id prefix, bins, capacity_l, (lat, lon) centre)
GROUPS = [
    ('hostel', 'Rajendra Bhawan', 'HA', 5, 240, (29.87101, 77.89408)),
    ('hostel', 'Rajiv Bhawan', 'HB', 5, 240, (29.86978, 77.89498)),
    ('hostel', 'Radhakrishnan Bhawan', 'HC', 5, 240, (29.87120, 77.89566)),
    ('hostel', 'Govind Bhawan', 'HD', 5, 240, (29.86203, 77.89447)),
    ('hostel', 'Kasturba Bhawan', 'HE', 5, 240, (29.86724, 77.90090)),
    ('hostel', 'Sarojini Bhawan', 'HF', 5, 240, (29.86505, 77.90003)),
    ('mess', 'Jawahar Bhawan Mess', 'M1', 2, 660, (29.86346, 77.90057)),
    ('mess', 'Cautley & Ganga Bhawan Mess', 'M2', 2, 660, (29.87199, 77.89520)),
    ('mess', 'Ravindra Bhawan Mess', 'M3', 2, 660, (29.86493, 77.89282)),
    ('mess_food', 'Jawahar Bhawan Mess', 'M1', 2, 120, (29.86346, 77.90057)),
    ('mess_food', 'Cautley & Ganga Bhawan Mess', 'M2', 2, 120, (29.87199, 77.89520)),
    ('mess_food', 'Ravindra Bhawan Mess', 'M3', 2, 120, (29.86493, 77.89282)),
    ('department', 'Civil Engineering Dept', 'D1', 2, 120, (29.86261, 77.89854)),
    ('department', 'Electrical Engineering Dept', 'D2', 2, 120, (29.86367, 77.89732)),
    ('department', 'Mechanical & Industrial Engg Dept', 'D3', 2, 120, (29.86221, 77.89782)),
    ('department', 'Computer Science & Engg Dept', 'D4', 2, 120, (29.86351, 77.89591)),
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
