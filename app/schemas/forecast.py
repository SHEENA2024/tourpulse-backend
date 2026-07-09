from pydantic import BaseModel
from typing import Optional


# ── Single prediction response ─────────────────────────────────────────────
class ShapFactor(BaseModel):
    feature:       str
    shap_value:    float
    feature_value: float
    direction:     str        # "positive" | "negative"
    impact_pct:    float


class ModelInfo(BaseModel):
    model_name:    str
    model_version: str
    trained_at:    str
    test_mae:      float
    test_rmse:     float
    test_mape:     float
    test_r2:       float


class PredictionResponse(BaseModel):
    place_name:   str
    city:         str
    category:     str
    forecast_date: str
    day_of_week:  str
    is_weekend:   bool
    season:       str

    demand_score:  float
    demand_label:  str       # High / Moderate / Low
    base_score:    float
    confidence_pct: float

    hotel_occupancy_pct:    float
    hotel_occupancy_label:  str
    transport_demand_index: float
    transport_demand_label: str

    shap_top_factors: list[ShapFactor]
    shap_base_value:  float

    inputs:     dict
    model_info: ModelInfo


# ── Multi-day forecast ─────────────────────────────────────────────────────
class DayForecast(BaseModel):
    date:          str
    day_of_week:   str
    is_weekend:    bool
    is_holiday:    bool
    holiday_name:  str
    is_event:      bool
    event_name:    str
    demand_score:  float
    demand_label:  str
    hotel_occupancy_pct:    float
    transport_demand_index: float
    confidence_pct: float
    top_factor:     str
    temperature_c:  float
    weather_condition: str


class ForecastSummary(BaseModel):
    avg_demand_score:    float
    peak_demand_score:   float
    peak_date:           str
    trough_demand_score: float
    trough_date:         str
    avg_hotel_occupancy: float
    avg_transport_index: float
    holiday_count:       int
    event_count:         int


class ForecastResponse(BaseModel):
    city:         str
    place_name:   str
    horizon_days: int
    generated_at: str
    forecasts:    list[DayForecast]
    summary:      ForecastSummary


# ── Heatmap ────────────────────────────────────────────────────────────────
class HeatmapPoint(BaseModel):
    city:          str
    place_name:    str
    category:      str
    latitude:      float
    longitude:     float
    demand_score:  float
    demand_label:  str
    hotel_occupancy_pct:    float
    transport_demand_index: float


class HeatmapResponse(BaseModel):
    date:         str
    generated_at: str
    points:       list[HeatmapPoint]
    summary: dict


# ── Places list ────────────────────────────────────────────────────────────
class PlaceInfo(BaseModel):
    place_id:      str
    place_name:    str
    city:          str
    state:         str
    category:      str
    latitude:      Optional[float]
    longitude:     Optional[float]
    avg_rating:    float
    entry_fee_inr: float
