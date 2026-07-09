"""
Admin endpoints — manage events, holidays, weather overrides.
All write endpoints require X-Admin-Key header.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Event, Holiday
from app.schemas.admin import (
    EventCreate, EventResponse,
    HolidayCreate, HolidayResponse,
)
from app.core.config import settings

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def _require_admin(x_admin_key: str = Header(default=None)):
    if x_admin_key != settings.admin_secret_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Key header")


# ── Events ────────────────────────────────────────────────────────────────────
@router.get("/events", response_model=list[EventResponse])
def list_events(city: str = None, db: Session = Depends(get_db)):
    q = db.query(Event)
    if city:
        q = q.filter(Event.city == city)
    return q.order_by(Event.event_date.desc()).all()


@router.post("/events", response_model=EventResponse)
def create_event(
    payload: EventCreate,
    db:      Session = Depends(get_db),
    _auth:   None    = Depends(_require_admin),
):
    event = Event(**payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.put("/events/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    payload:  EventCreate,
    db:       Session = Depends(get_db),
    _auth:    None    = Depends(_require_admin),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    for k, v in payload.model_dump().items():
        setattr(event, k, v)
    db.commit()
    db.refresh(event)
    return event


@router.delete("/events/{event_id}")
def delete_event(
    event_id: int,
    db:       Session = Depends(get_db),
    _auth:    None    = Depends(_require_admin),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(event)
    db.commit()
    return {"deleted": event_id}


# ── Holidays ──────────────────────────────────────────────────────────────────
@router.get("/holidays", response_model=list[HolidayResponse])
def list_holidays(db: Session = Depends(get_db)):
    return db.query(Holiday).order_by(Holiday.holiday_date.desc()).all()


@router.post("/holidays", response_model=HolidayResponse)
def create_holiday(
    payload: HolidayCreate,
    db:      Session = Depends(get_db),
    _auth:   None    = Depends(_require_admin),
):
    existing = db.query(Holiday).filter(
        Holiday.holiday_date == payload.holiday_date
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Holiday already exists for {payload.holiday_date}"
        )
    holiday = Holiday(**payload.model_dump())
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.delete("/holidays/{holiday_id}")
def delete_holiday(
    holiday_id: int,
    db:         Session = Depends(get_db),
    _auth:      None    = Depends(_require_admin),
):
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(holiday)
    db.commit()
    return {"deleted": holiday_id}


# ── City factors (read-only from config, updatable via env in production) ─────
@router.get("/config/city-factors")
def get_city_factors():
    return {"city_factors": settings.city_factors}
