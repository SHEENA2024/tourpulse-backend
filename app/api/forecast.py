"""
Forecast API endpoints.
GET /api/places                        — list all cities and places
GET /api/forecast/{city}/{place_name}  — multi-day forecast
GET /api/heatmap                       — all cities for a given date
"""
import logging
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.predictor import predict_demand, forecast_horizon
from app.services.weather import fetch_weather_forecast
from app.services.holidays import build_holidays_map, build_events_map

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Forecast"])

# ── Static place catalogue (from the training dataset) ────────────────────────
PLACES = [
    {"place_id":"PL001","place_name":"Rose Garden",       "city":"Ooty",      "state":"Tamil Nadu",      "category":"Natural",  "latitude":11.417,  "longitude":76.707, "avg_rating":4.3,"entry_fee_inr":30.0},
    {"place_id":"PL002","place_name":"Botanical Garden",  "city":"Ooty",      "state":"Tamil Nadu",      "category":"Natural",  "latitude":11.408,  "longitude":76.695, "avg_rating":4.4,"entry_fee_inr":30.0},
    {"place_id":"PL003","place_name":"Doddabetta Peak",   "city":"Ooty",      "state":"Tamil Nadu",      "category":"Natural",  "latitude":11.406,  "longitude":76.740, "avg_rating":4.2,"entry_fee_inr":0.0},
    {"place_id":"PL004","place_name":"Nilgiri Mountain Railway","city":"Ooty","state":"Tamil Nadu",      "category":"Historic", "latitude":11.412,  "longitude":76.695, "avg_rating":4.6,"entry_fee_inr":40.0},
    {"place_id":"PL005","place_name":"Ooty Lake",         "city":"Ooty",      "state":"Tamil Nadu",      "category":"Natural",  "latitude":11.405,  "longitude":76.695, "avg_rating":4.0,"entry_fee_inr":0.0},
    {"place_id":"PL006","place_name":"Thunder World",     "city":"Ooty",      "state":"Tamil Nadu",      "category":"Cultural", "latitude":11.416,  "longitude":76.698, "avg_rating":3.9,"entry_fee_inr":150.0},
    {"place_id":"PL007","place_name":"Meenakshi Temple",  "city":"Madurai",   "state":"Tamil Nadu",      "category":"Religious","latitude":9.9195,  "longitude":78.1193,"avg_rating":4.7,"entry_fee_inr":0.0},
    {"place_id":"PL008","place_name":"Gandhi Museum",     "city":"Madurai",   "state":"Tamil Nadu",      "category":"Cultural", "latitude":9.9186,  "longitude":78.1123,"avg_rating":4.0,"entry_fee_inr":150.0},
    {"place_id":"PL009","place_name":"Samanar Hills",     "city":"Madurai",   "state":"Tamil Nadu",      "category":"Natural",  "latitude":9.9637,  "longitude":77.9682,"avg_rating":4.2,"entry_fee_inr":30.0},
    {"place_id":"PL010","place_name":"Thirumalai Nayakkar Palace","city":"Madurai","state":"Tamil Nadu", "category":"Historic", "latitude":9.9178,  "longitude":78.1245,"avg_rating":4.3,"entry_fee_inr":50.0},
    {"place_id":"PL011","place_name":"Alagar Kovil",      "city":"Madurai",   "state":"Tamil Nadu",      "category":"Religious","latitude":10.0698, "longitude":78.0718,"avg_rating":4.5,"entry_fee_inr":0.0},
    {"place_id":"PL012","place_name":"Taj Mahal",         "city":"Agra",      "state":"Uttar Pradesh",   "category":"Monument", "latitude":27.1751, "longitude":78.0421,"avg_rating":4.8,"entry_fee_inr":1100.0},
    {"place_id":"PL013","place_name":"Red Fort",          "city":"Delhi",     "state":"Delhi",           "category":"Historic", "latitude":28.6562, "longitude":77.2410,"avg_rating":4.5,"entry_fee_inr":250.0},
    {"place_id":"PL014","place_name":"Qutub Minar",       "city":"Delhi",     "state":"Delhi",           "category":"Historic", "latitude":28.5245, "longitude":77.1855,"avg_rating":4.4,"entry_fee_inr":35.0},
    {"place_id":"PL015","place_name":"India Gate",        "city":"Delhi",     "state":"Delhi",           "category":"Monument", "latitude":28.6129, "longitude":77.2295,"avg_rating":4.3,"entry_fee_inr":0.0},
    {"place_id":"PL016","place_name":"Humayun's Tomb",    "city":"Delhi",     "state":"Delhi",           "category":"Historic", "latitude":28.5933, "longitude":77.2507,"avg_rating":4.6,"entry_fee_inr":35.0},
    {"place_id":"PL017","place_name":"Lotus Temple",      "city":"Delhi",     "state":"Delhi",           "category":"Religious","latitude":28.5535, "longitude":77.2588,"avg_rating":4.5,"entry_fee_inr":0.0},
    {"place_id":"PL018","place_name":"Amber Fort",        "city":"Jaipur",    "state":"Rajasthan",       "category":"Historic", "latitude":26.9855, "longitude":75.8513,"avg_rating":4.6,"entry_fee_inr":200.0},
    {"place_id":"PL019","place_name":"City Palace Jaipur","city":"Jaipur",    "state":"Rajasthan",       "category":"Historic", "latitude":26.9258, "longitude":75.8237,"avg_rating":4.5,"entry_fee_inr":200.0},
    {"place_id":"PL020","place_name":"Hawa Mahal",        "city":"Jaipur",    "state":"Rajasthan",       "category":"Historic", "latitude":26.9239, "longitude":75.8267,"avg_rating":4.5,"entry_fee_inr":50.0},
    {"place_id":"PL021","place_name":"Jantar Mantar Jaipur","city":"Jaipur",  "state":"Rajasthan",       "category":"Monument", "latitude":26.9247, "longitude":75.8242,"avg_rating":4.3,"entry_fee_inr":50.0},
    {"place_id":"PL022","place_name":"Nahargarh Fort",    "city":"Jaipur",    "state":"Rajasthan",       "category":"Historic", "latitude":26.9380, "longitude":75.8121,"avg_rating":4.4,"entry_fee_inr":50.0},
    {"place_id":"PL023","place_name":"Gateway of India",  "city":"Mumbai",    "state":"Maharashtra",     "category":"Monument", "latitude":18.9220, "longitude":72.8347,"avg_rating":4.5,"entry_fee_inr":0.0},
    {"place_id":"PL024","place_name":"Marine Drive",      "city":"Mumbai",    "state":"Maharashtra",     "category":"Natural",  "latitude":18.9437, "longitude":72.8231,"avg_rating":4.4,"entry_fee_inr":0.0},
    {"place_id":"PL025","place_name":"Siddhivinayak Temple","city":"Mumbai",  "state":"Maharashtra",     "category":"Religious","latitude":19.0168, "longitude":72.8304,"avg_rating":4.6,"entry_fee_inr":0.0},
    {"place_id":"PL026","place_name":"Elephanta Caves",   "city":"Mumbai",    "state":"Maharashtra",     "category":"Historic", "latitude":18.9633, "longitude":72.9315,"avg_rating":4.3,"entry_fee_inr":600.0},
    {"place_id":"PL027","place_name":"Chhatrapati Shivaji Museum","city":"Mumbai","state":"Maharashtra", "category":"Cultural", "latitude":18.9271, "longitude":72.8325,"avg_rating":4.5,"entry_fee_inr":85.0},
    {"place_id":"PL028","place_name":"Victoria Memorial", "city":"Kolkata",   "state":"West Bengal",     "category":"Historic", "latitude":22.5448, "longitude":88.3426,"avg_rating":4.6,"entry_fee_inr":30.0},
    {"place_id":"PL029","place_name":"Indian Museum",     "city":"Kolkata",   "state":"West Bengal",     "category":"Cultural", "latitude":22.5575, "longitude":88.3472,"avg_rating":4.3,"entry_fee_inr":20.0},
    {"place_id":"PL030","place_name":"Howrah Bridge",     "city":"Kolkata",   "state":"West Bengal",     "category":"Monument", "latitude":22.5851, "longitude":88.3468,"avg_rating":4.4,"entry_fee_inr":0.0},
    {"place_id":"PL031","place_name":"Dakshineswar Temple","city":"Kolkata",  "state":"West Bengal",     "category":"Religious","latitude":22.6550, "longitude":88.3577,"avg_rating":4.6,"entry_fee_inr":0.0},
    {"place_id":"PL032","place_name":"Charminar",         "city":"Hyderabad", "state":"Telangana",       "category":"Monument", "latitude":17.3616, "longitude":78.4747,"avg_rating":4.4,"entry_fee_inr":25.0},
    {"place_id":"PL033","place_name":"Golconda Fort",     "city":"Hyderabad", "state":"Telangana",       "category":"Historic", "latitude":17.3833, "longitude":78.4011,"avg_rating":4.5,"entry_fee_inr":15.0},
    {"place_id":"PL034","place_name":"Mysore Palace",     "city":"Mysore",    "state":"Karnataka",       "category":"Historic", "latitude":12.3052, "longitude":76.6552,"avg_rating":4.7,"entry_fee_inr":100.0},
    {"place_id":"PL035","place_name":"Chamundi Hills",    "city":"Mysore",    "state":"Karnataka",       "category":"Religious","latitude":12.2723, "longitude":76.6697,"avg_rating":4.5,"entry_fee_inr":0.0},
    {"place_id":"PL036","place_name":"Alleppey Backwaters","city":"Alleppey", "state":"Kerala",          "category":"Natural",  "latitude":9.4981,  "longitude":76.3388,"avg_rating":4.7,"entry_fee_inr":0.0},
    {"place_id":"PL037","place_name":"Golden Temple",     "city":"Amritsar",  "state":"Punjab",          "category":"Religious","latitude":31.6200, "longitude":74.8765,"avg_rating":4.9,"entry_fee_inr":0.0},
    {"place_id":"PL038","place_name":"Jallianwala Bagh",  "city":"Amritsar",  "state":"Punjab",          "category":"Historic", "latitude":31.6200, "longitude":74.8762,"avg_rating":4.7,"entry_fee_inr":0.0},
    {"place_id":"PL039","place_name":"Kashi Vishwanath Temple","city":"Varanasi","state":"Uttar Pradesh","category":"Religious","latitude":25.3109, "longitude":83.0104,"avg_rating":4.7,"entry_fee_inr":0.0},
    {"place_id":"PL040","place_name":"Dashashwamedh Ghat","city":"Varanasi",  "state":"Uttar Pradesh",   "category":"Religious","latitude":25.3059, "longitude":83.0104,"avg_rating":4.6,"entry_fee_inr":0.0},
    {"place_id":"PL041","place_name":"Rohtang Pass",      "city":"Manali",    "state":"Himachal Pradesh","category":"Adventure","latitude":32.3716, "longitude":77.2429,"avg_rating":4.5,"entry_fee_inr":0.0},
    {"place_id":"PL042","place_name":"Solang Valley",     "city":"Manali",    "state":"Himachal Pradesh","category":"Adventure","latitude":32.3196, "longitude":77.1515,"avg_rating":4.4,"entry_fee_inr":0.0},
    {"place_id":"PL043","place_name":"Dal Lake",          "city":"Srinagar",  "state":"Jammu & Kashmir", "category":"Natural",  "latitude":34.1211, "longitude":74.8805,"avg_rating":4.6,"entry_fee_inr":0.0},
    {"place_id":"PL044","place_name":"Gulmarg Gondola",   "city":"Gulmarg",   "state":"Jammu & Kashmir", "category":"Adventure","latitude":34.0484, "longitude":74.3805,"avg_rating":4.7,"entry_fee_inr":900.0},
]

# Build lookup maps
PLACES_BY_CITY: dict[str, list] = {}
PLACE_LOOKUP: dict[tuple, dict] = {}

for p in PLACES:
    PLACES_BY_CITY.setdefault(p["city"], []).append(p)
    PLACE_LOOKUP[(p["city"].lower(), p["place_name"].lower())] = p


def _get_place(city: str, place_name: str) -> dict:
    key = (city.lower(), place_name.lower())
    if key in PLACE_LOOKUP:
        return PLACE_LOOKUP[key]
    # Fallback: first place in city
    city_places = PLACES_BY_CITY.get(city, [])
    if city_places:
        return city_places[0]
    raise HTTPException(status_code=404, detail=f"City '{city}' not found")


# ── GET /api/places ────────────────────────────────────────────────────────────
@router.get("/places")
def list_places():
    """Returns all tracked cities and their places."""
    result = {}
    for city, places in PLACES_BY_CITY.items():
        result[city] = [
            {"place_id": p["place_id"], "place_name": p["place_name"],
             "category": p["category"], "avg_rating": p["avg_rating"]}
            for p in places
        ]
    return {"cities": list(PLACES_BY_CITY.keys()), "places_by_city": result}


# ── GET /api/forecast/{city}/{place_name} ─────────────────────────────────────
@router.get("/forecast/{city}/{place_name}")
async def get_forecast(
    city:       str,
    place_name: str,
    horizon:    int = Query(default=7, ge=1, le=30, description="Forecast days (1–30)"),
    db: Session = Depends(get_db),
):
    place = _get_place(city, place_name)

    # Fetch weather for horizon days
    weather = await fetch_weather_forecast(city, horizon, db)

    # Build dates list
    dates = [w["date"] for w in weather]

    # Build holiday + event maps
    holidays_map = build_holidays_map(dates, db)
    events_map   = build_events_map(city, dates, db)

    # Default lag values (use training distribution averages as baseline)
    default_lags = {"lag_1_demand": 70.0, "lag_7_demand": 68.0,
                    "rolling_avg_7": 69.0, "lag_1_crowd": 2.0}

    result = forecast_horizon(
        city=city, place_name=place["place_name"],
        category=place["category"],
        avg_rating=place["avg_rating"],
        entry_fee_inr=place["entry_fee_inr"],
        weather_forecasts=weather,
        holidays_map=holidays_map,
        events_map=events_map,
        last_demand_scores=[default_lags["lag_1_demand"]] * 7,
        last_crowd_numerics=[default_lags["lag_1_crowd"]],
        horizon_days=horizon,
    )
    return result


# ── GET /api/heatmap ──────────────────────────────────────────────────────────
@router.get("/heatmap")
async def get_heatmap(
    target_date: str = Query(default=None, description="YYYY-MM-DD (defaults to today)"),
    db: Session = Depends(get_db),
):
    if target_date is None:
        target_date = date.today().isoformat()

    holidays_map = build_holidays_map([target_date], db)
    is_holiday   = 1 if target_date in holidays_map else 0

    points = []
    for place in PLACES:
        city = place["city"]
        events_map = build_events_map(city, [target_date], db)
        is_event   = 1 if target_date in events_map else 0

        try:
            weather = await fetch_weather_forecast(city, 1, db)
            w = weather[0] if weather else {}
        except Exception:
            w = {}

        result = predict_demand(
            city=city,
            place_name=place["place_name"],
            category=place["category"],
            forecast_date=target_date,
            temperature_c  = w.get("temperature_c",           28.0),
            rainfall_mm    = w.get("rainfall_mm",              2.0),
            humidity_pct   = w.get("humidity_pct",            65.0),
            weather_suit   = w.get("weather_suitability_score", 0.65),
            is_holiday=is_holiday, is_event=is_event,
            lag_1_demand=70.0, lag_7_demand=68.0,
            rolling_avg_7=69.0, lag_1_crowd=2.0,
            avg_rating=place["avg_rating"],
            entry_fee_inr=place["entry_fee_inr"],
        )

        points.append({
            "city":          city,
            "place_name":    place["place_name"],
            "category":      place["category"],
            "latitude":      place.get("latitude") or 0.0,
            "longitude":     place.get("longitude") or 0.0,
            "demand_score":  result["demand_score"],
            "demand_label":  result["demand_label"],
            "hotel_occupancy_pct":    result["hotel_occupancy_pct"],
            "transport_demand_index": result["transport_demand_index"],
        })

    all_scores = [p["demand_score"] for p in points]
    return {
        "date":         target_date,
        "generated_at": datetime.now().isoformat(),
        "points":       points,
        "summary": {
            "avg_demand":  round(sum(all_scores) / len(all_scores), 1) if all_scores else 0,
            "max_demand":  max(all_scores) if all_scores else 0,
            "min_demand":  min(all_scores) if all_scores else 0,
            "total_places": len(points),
        },
    }
