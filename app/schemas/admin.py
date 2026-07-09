from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EventCreate(BaseModel):
    city:        str
    place_name:  Optional[str] = None
    event_name:  str
    event_date:  str          # YYYY-MM-DD
    category:    str = "Cultural"
    description: Optional[str] = None


class EventResponse(BaseModel):
    id:          int
    city:        str
    place_name:  Optional[str]
    event_name:  str
    event_date:  str
    category:    str
    description: Optional[str]
    created_at:  datetime

    class Config:
        from_attributes = True


class HolidayCreate(BaseModel):
    holiday_date: str          # YYYY-MM-DD
    holiday_name: str
    region:       str = "India"


class HolidayResponse(BaseModel):
    id:           int
    holiday_date: str
    holiday_name: str
    region:       str
    created_at:   datetime

    class Config:
        from_attributes = True


class MLOpsStatus(BaseModel):
    model_name:      str
    model_version:   str
    trained_at:      str
    test_mae:        float
    test_rmse:       float
    test_mape:       float
    test_r2:         float
    drift_status:    str
    drift_score:     Optional[float]
    last_drift_check: Optional[str]
    last_retrain:    Optional[str]
    retrain_outcome: Optional[str]
    is_model_loaded: bool
