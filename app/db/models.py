from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from app.db.database import Base


class Event(Base):
    __tablename__ = "events"

    id          = Column(Integer, primary_key=True, index=True)
    city        = Column(String(100), nullable=False, index=True)
    place_name  = Column(String(200), nullable=True)
    event_name  = Column(String(200), nullable=False)
    event_date  = Column(String(10), nullable=False)   # YYYY-MM-DD
    category    = Column(String(100), default="Cultural")
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


class Holiday(Base):
    __tablename__ = "holidays"

    id           = Column(Integer, primary_key=True, index=True)
    holiday_date = Column(String(10), nullable=False, unique=True)  # YYYY-MM-DD
    holiday_name = Column(String(200), nullable=False)
    region       = Column(String(100), default="India")
    created_at   = Column(DateTime, default=datetime.utcnow)


class DriftReport(Base):
    __tablename__ = "drift_reports"

    id           = Column(Integer, primary_key=True, index=True)
    run_at       = Column(DateTime, default=datetime.utcnow)
    drift_score  = Column(Float, nullable=True)
    mae_current  = Column(Float, nullable=True)
    status       = Column(String(20), default="ok")   # ok / warning / critical
    details      = Column(Text, nullable=True)         # JSON string


class RetrainLog(Base):
    __tablename__ = "retrain_log"

    id           = Column(Integer, primary_key=True, index=True)
    triggered_by = Column(String(50), default="manual")   # manual / drift / scheduled
    started_at   = Column(DateTime, default=datetime.utcnow)
    finished_at  = Column(DateTime, nullable=True)
    outcome      = Column(String(20), nullable=True)       # promoted / rejected / failed
    old_mae      = Column(Float, nullable=True)
    new_mae      = Column(Float, nullable=True)
    notes        = Column(Text, nullable=True)


class WeatherCache(Base):
    __tablename__ = "weather_cache"

    id           = Column(Integer, primary_key=True, index=True)
    city         = Column(String(100), nullable=False, index=True)
    forecast_date = Column(String(10), nullable=False)   # YYYY-MM-DD
    temperature_c = Column(Float, nullable=True)
    rainfall_mm   = Column(Float, nullable=True)
    humidity_pct  = Column(Float, nullable=True)
    weather_suitability = Column(Float, nullable=True)
    weather_condition   = Column(String(50), nullable=True)
    fetched_at    = Column(DateTime, default=datetime.utcnow)
