"""Routing data types (SPEC Section 15)."""
from dataclasses import dataclass, field

from app import config


@dataclass
class Stop:
    bin_id: str
    name: str
    lat: float
    lon: float
    stream: str          # 'general' or 'food'
    demand_l: float


@dataclass
class RoutingSettings:
    vehicles: list[dict] = field(default_factory=lambda: [dict(v) for v in config.VEHICLES])
    nodes: list[dict] = field(default_factory=lambda: [dict(n) for n in config.NODES])
    detour_factor: float = config.DETOUR_FACTOR
    speed_kmph: float = config.SPEED_KMPH
    service_min_per_bin: float = config.SERVICE_MIN_PER_BIN
    shift_min: float = config.SHIFT_MIN
    capacity_buffer: float = config.CAPACITY_BUFFER

    def vehicles_for(self, k: int) -> list[dict]:
        """Vehicles for fleet size k = the first k vehicles."""
        if not 1 <= k <= len(self.vehicles):
            raise ValueError(f"fleet size must be 1..{len(self.vehicles)}, got {k}")
        return self.vehicles[:k]
