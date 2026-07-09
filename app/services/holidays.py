"""
Returns holiday and event flags for a given date range.
Holidays: Python `holidays` library (Indian public holidays) + DB overrides.
Events:   Admin-entered via the /admin/events endpoint stored in SQLite.
"""
import holidays as hol_lib
import logging
from sqlalchemy.orm import Session
from app.db.models import Holiday, Event

logger = logging.getLogger(__name__)

EXTRA_HOLIDAYS = {
    # Diwali
    "2019-10-27": "Diwali", "2020-11-14": "Diwali", "2021-11-04": "Diwali",
    "2022-10-24": "Diwali", "2023-11-12": "Diwali", "2024-11-01": "Diwali",
    "2025-10-20": "Diwali", "2026-11-08": "Diwali",
    # Holi
    "2019-03-21": "Holi", "2020-03-10": "Holi", "2021-03-29": "Holi",
    "2022-03-18": "Holi", "2023-03-08": "Holi", "2024-03-25": "Holi",
    "2025-03-14": "Holi", "2026-03-03": "Holi",
    # Pongal / Makar Sankranti
    **{f"{y}-01-14": "Pongal" for y in range(2019, 2027)},
    # Christmas & New Year
    **{f"{y}-12-25": "Christmas" for y in range(2019, 2027)},
    **{f"{y}-01-01": "New Year's Day" for y in range(2019, 2027)},
    # Navratri / Dussehra (approx)
    "2019-10-07": "Navratri", "2020-10-25": "Navratri", "2021-10-15": "Navratri",
    "2022-10-02": "Navratri", "2023-10-20": "Navratri", "2024-10-10": "Navratri",
    "2025-09-29": "Navratri", "2026-10-18": "Navratri",
}


def build_holidays_map(dates: list[str], db: Session) -> dict[str, str]:
    """
    Returns {date_str: holiday_name} for all holiday dates in the list.
    Merges: Python library holidays + EXTRA_HOLIDAYS + admin DB holidays.
    """
    result = {}

    years = {int(d[:4]) for d in dates}
    lib_holidays = {}
    for year in years:
        lib_holidays.update({
            str(k): v for k, v in hol_lib.India(years=year).items()
        })

    lib_holidays.update(EXTRA_HOLIDAYS)

    for d in dates:
        if d in lib_holidays:
            result[d] = lib_holidays[d]

    # Admin-added holidays from DB
    db_holidays = db.query(Holiday).filter(Holiday.holiday_date.in_(dates)).all()
    for h in db_holidays:
        result[h.holiday_date] = h.holiday_name

    return result


def build_events_map(city: str, dates: list[str], db: Session) -> dict[str, str]:
    """
    Returns {date_str: event_name} for events in the given city on those dates.
    """
    events = db.query(Event).filter(
        Event.city == city,
        Event.event_date.in_(dates)
    ).all()

    return {e.event_date: e.event_name for e in events}
