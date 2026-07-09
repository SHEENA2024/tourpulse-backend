"""
Fetches weather forecasts from Open-Meteo (free, no API key).
Results are cached in SQLite to avoid hammering the API on every request.
Cache is considered fresh for 6 hours.
"""
import httpx
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.models import WeatherCache

logger = logging.getLogger(__name__)

# GPS coordinates for each tracked city
CITY_COORDS = {
    "Ooty":      {"lat": 11.4102, "lon": 76.6950},
    "Manali":    {"lat": 32.2432, "lon": 77.1892},
    "Gulmarg":   {"lat": 34.0484, "lon": 74.3805},
    "Srinagar":  {"lat": 34.0837, "lon": 74.7973},
    "Jaipur":    {"lat": 26.9124, "lon": 75.7873},
    "Agra":      {"lat": 27.1767, "lon": 78.0081},
    "Delhi":     {"lat": 28.6139, "lon": 77.2090},
    "Mumbai":    {"lat": 19.0760, "lon": 72.8777},
    "Kolkata":   {"lat": 22.5726, "lon": 88.3639},
    "Hyderabad": {"lat": 17.3850, "lon": 78.4867},
    "Mysore":    {"lat": 12.2958, "lon": 76.6394},
    "Alleppey":  {"lat": 9.4981,  "lon": 76.3388},
    "Madurai":   {"lat": 9.9252,  "lon": 78.1198},
    "Varanasi":  {"lat": 25.3176, "lon": 82.9739},
    "Amritsar":  {"lat": 31.6340, "lon": 74.8723},
}

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_TTL_HOURS = 6


def _weather_suitability(temp: float, rain: float, humidity: float) -> float:
    """
    Compute a 0–1 suitability score from raw weather values.
    Logic mirrors what was used during dataset creation.
    """
    # Temperature score: ideal 18–28°C
    if 18 <= temp <= 28:
        temp_score = 1.0
    elif temp < 18:
        temp_score = max(0.0, 1.0 - (18 - temp) / 15)
    else:
        temp_score = max(0.0, 1.0 - (temp - 28) / 15)

    # Rain score: 0mm = 1.0, 20mm+ = 0.0
    rain_score = max(0.0, 1.0 - rain / 20)

    # Humidity score: ideal 40–65%
    if 40 <= humidity <= 65:
        hum_score = 1.0
    elif humidity < 40:
        hum_score = max(0.0, humidity / 40)
    else:
        hum_score = max(0.0, 1.0 - (humidity - 65) / 35)

    return round(0.4 * temp_score + 0.4 * rain_score + 0.2 * hum_score, 4)


def _condition_label(rain: float, temp: float) -> str:
    if rain > 10:
        return "Heavy Rain"
    elif rain > 2:
        return "Light Rain"
    elif temp > 35:
        return "Hot & Sunny"
    elif temp < 10:
        return "Cold & Clear"
    else:
        return "Sunny"


def _cache_is_fresh(fetched_at: datetime) -> bool:
    return (datetime.utcnow() - fetched_at) < timedelta(hours=CACHE_TTL_HOURS)


async def fetch_weather_forecast(city: str, days: int, db: Session) -> list[dict]:
    """
    Returns a list of weather dicts for `days` days starting from today.
    Checks SQLite cache first; fetches from Open-Meteo if stale/missing.
    """
    if city not in CITY_COORDS:
        logger.warning("Unknown city for weather: %s — using defaults", city)
        return _default_weather(city, days)

    coords  = CITY_COORDS[city]
    today   = datetime.utcnow().date()
    dates   = [(today + timedelta(days=i)).isoformat() for i in range(days)]

    # Check cache
    cached = {
        row.forecast_date: row
        for row in db.query(WeatherCache)
        .filter(WeatherCache.city == city, WeatherCache.forecast_date.in_(dates))
        .all()
    }

    fresh = {d: cached[d] for d in dates if d in cached and _cache_is_fresh(cached[d].fetched_at)}

    if len(fresh) == days:
        logger.debug("Weather cache hit for %s (%d days)", city, days)
        return _rows_to_dicts(dates, fresh)

    # Fetch from Open-Meteo
    logger.info("Fetching weather from Open-Meteo for %s (%d days)", city, days)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(OPEN_METEO_URL, params={
                "latitude":           coords["lat"],
                "longitude":          coords["lon"],
                "daily":              "temperature_2m_max,temperature_2m_min,precipitation_sum,relative_humidity_2m_max",
                "forecast_days":      min(days, 16),
                "timezone":           "Asia/Kolkata",
            })
            resp.raise_for_status()
            data = resp.json()

        daily    = data["daily"]
        api_dates = daily["time"]

        for i, d in enumerate(api_dates):
            if d not in dates:
                continue
            temp  = round((daily["temperature_2m_max"][i] + daily["temperature_2m_min"][i]) / 2, 1)
            rain  = round(daily["precipitation_sum"][i] or 0.0, 1)
            hum   = round(daily["relative_humidity_2m_max"][i] or 65.0, 1)
            suit  = _weather_suitability(temp, rain, hum)
            cond  = _condition_label(rain, temp)

            # Upsert cache
            existing = db.query(WeatherCache).filter(
                WeatherCache.city == city,
                WeatherCache.forecast_date == d
            ).first()
            if existing:
                existing.temperature_c = temp
                existing.rainfall_mm   = rain
                existing.humidity_pct  = hum
                existing.weather_suitability = suit
                existing.weather_condition   = cond
                existing.fetched_at    = datetime.utcnow()
            else:
                db.add(WeatherCache(
                    city=city, forecast_date=d,
                    temperature_c=temp, rainfall_mm=rain,
                    humidity_pct=hum, weather_suitability=suit,
                    weather_condition=cond,
                ))
        db.commit()

        # Re-query fresh cache
        fresh = {
            row.forecast_date: row
            for row in db.query(WeatherCache)
            .filter(WeatherCache.city == city, WeatherCache.forecast_date.in_(dates))
            .all()
        }
        return _rows_to_dicts(dates, fresh)

    except Exception as e:
        logger.error("Open-Meteo fetch failed: %s — using defaults", e)
        return _default_weather(city, days)


def _rows_to_dicts(dates: list[str], cache: dict) -> list[dict]:
    result = []
    for d in dates:
        row = cache.get(d)
        if row:
            result.append({
                "date":                    d,
                "temperature_c":           row.temperature_c or 28.0,
                "rainfall_mm":             row.rainfall_mm or 2.0,
                "humidity_pct":            row.humidity_pct or 65.0,
                "weather_suitability_score": row.weather_suitability or 0.65,
                "weather_condition":       row.weather_condition or "Sunny",
            })
        else:
            result.append(_default_day(d))
    return result


def _default_weather(city: str, days: int) -> list[dict]:
    from datetime import date
    today = date.today()
    return [_default_day((today + timedelta(days=i)).isoformat()) for i in range(days)]


def _default_day(date_str: str) -> dict:
    return {
        "date": date_str,
        "temperature_c": 28.0,
        "rainfall_mm":   2.0,
        "humidity_pct":  65.0,
        "weather_suitability_score": 0.65,
        "weather_condition": "Sunny",
    }
