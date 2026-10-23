"""Pydantic v2 request bodies (SPEC Section 14). Invalid bodies -> HTTP 422."""
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.config import DEFAULT_TAU, FLEET_SIZES, TAU_MAX, TAU_MIN

Level = Literal["low", "medium", "full"]
Tau = Annotated[float, Field(ge=TAU_MIN, le=TAU_MAX)]
FleetSize = Annotated[int, Field(ge=min(FLEET_SIZES), le=max(FLEET_SIZES))]


class ObservationIn(BaseModel):
    bin_id: str
    level: Level | None = None
    fill_pct: float | None = Field(None, ge=0, le=100)
    source: Literal["staff_tap", "camera", "simulated"] = "staff_tap"

    @model_validator(mode="after")
    def exactly_one_reading(self):
        if (self.level is None) == (self.fill_pct is None):
            raise ValueError("Give exactly one of level or fill_pct")
        return self


class DecisionsIn(BaseModel):
    tau: Tau = DEFAULT_TAU


class RoutesIn(BaseModel):
    tau: Tau = DEFAULT_TAU
    fleet_sizes: list[FleetSize] = Field(default_factory=lambda: list(FLEET_SIZES), min_length=1)
    fast: bool = False


class ChooseIn(BaseModel):
    fleet_size: FleetSize


class PickupIn(BaseModel):
    route_id: str
    bin_id: str
    level: Level | None = None
    staff_note: str | None = Field(None, max_length=300)


class CompostIn(BaseModel):
    route_id: str


class MessLogIn(BaseModel):
    mess_id: str
    meal: Literal["breakfast", "lunch", "snacks", "dinner"]
    category: Literal["plate", "kitchen_prep", "unserved"]
    weight_kg: float = Field(gt=0, le=500)
    weighed: bool
    date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    logged_by: str = "mess staff"
