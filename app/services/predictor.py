"""
Core prediction engine — adapted directly from the Jupyter notebook.
predict_demand() and forecast_horizon() are the two main functions.
Both use the global model_store (loaded once at startup).
"""
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from app.core.model_loader import model_store
from app.core.config import settings

logger = logging.getLogger(__name__)

SEASON_MAP = {
    3: "Spring", 4: "Spring", 5: "Spring",
    6: "Monsoon", 7: "Monsoon", 8: "Monsoon",
    9: "Autumn", 10: "Autumn", 11: "Autumn",
}


def _safe_encode(encoder, value: str) -> int:
    if value in encoder.classes_:
        return int(encoder.transform([value])[0])
    logger.warning("Unknown label '%s' for encoder — using fallback", value)
    return int(encoder.transform([encoder.classes_[0]])[0])


def _demand_label(score: float) -> str:
    if score >= 70:   return "High"
    if score >= 40:   return "Moderate"
    return "Low"


def _derive_resources(demand_score: float, city: str) -> dict:
    factors = settings.city_factors.get(city, [0.78, 0.80])
    occ_f, trans_f = factors[0], factors[1]

    hotel_pct  = round(min(100.0, demand_score * occ_f), 1)
    trans_idx  = round(min(100.0, demand_score * trans_f), 1)

    def label(v):
        return "High" if v >= 70 else "Moderate" if v >= 40 else "Low"

    return {
        "hotel_occupancy_pct":    hotel_pct,
        "hotel_occupancy_label":  label(hotel_pct),
        "transport_demand_index": trans_idx,
        "transport_demand_label": label(trans_idx),
    }


def predict_demand(
    city:          str,
    place_name:    str,
    category:      str,
    forecast_date: str,
    temperature_c: float,
    rainfall_mm:   float,
    humidity_pct:  float,
    weather_suit:  float,
    is_holiday:    int,
    is_event:      int,
    lag_1_demand:  float,
    lag_7_demand:  float,
    rolling_avg_7: float,
    lag_1_crowd:   float,
    avg_rating:    float,
    entry_fee_inr: float,
) -> dict:
    """
    Single-date prediction. Returns the full JSON dict that FastAPI
    sends directly to the React dashboard.
    """
    if not model_store.is_loaded:
        raise RuntimeError("Model not loaded — call model_store.load() at startup")

    model          = model_store.model
    label_encoders = model_store.label_encoders
    shap_exp       = model_store.shap_explainer
    metadata       = model_store.metadata

    dt     = pd.Timestamp(forecast_date)
    season = SEASON_MAP.get(dt.month, "Winter")

    feature_values = [
        dt.month,
        int(dt.isocalendar()[1]),
        dt.dayofweek,
        int(dt.dayofweek >= 5),
        temperature_c,
        rainfall_mm,
        humidity_pct,
        weather_suit,
        is_holiday,
        is_event,
        lag_1_demand,
        lag_7_demand,
        rolling_avg_7,
        lag_1_crowd,
        avg_rating,
        entry_fee_inr,
        _safe_encode(label_encoders["city"],     city),
        _safe_encode(label_encoders["category"], category),
        _safe_encode(label_encoders["season"],   season),
    ]

    X = pd.DataFrame([feature_values], columns=metadata["features"])

    raw   = float(model.predict(X)[0])
    score = round(max(0.0, min(100.0, raw)), 2)

    # SHAP
    if shap_exp is None:
        shap_contributions = []
        base_val = 0.0
    else:
        shap_vals = shap_exp.shap_values(X)[0]
        base_val  = float(shap_exp.expected_value)
        total     = float(np.abs(shap_vals).sum()) + 1e-9

        shap_contributions = sorted([
            {
                "feature":       name,
                "shap_value":    round(float(sv), 3),
                "feature_value": round(float(fv), 4),
                "direction":     "positive" if sv > 0 else "negative",
                "impact_pct":    round(abs(float(sv)) / total * 100, 1),
            }
            for name, sv, fv in zip(metadata["features"], shap_vals, feature_values)
        ], key=lambda x: abs(x["shap_value"]), reverse=True)

    resources = _derive_resources(score, city)

    test_r2 = metadata["metrics"]["test"]["r2"]
    confidence = round(
        min(99.0, max(50.0, test_r2 * 100 - abs(score - rolling_avg_7) * 0.3)), 1
    )

    return {
        "place_name":    place_name,
        "city":          city,
        "category":      category,
        "forecast_date": forecast_date,
        "day_of_week":   dt.day_name(),
        "is_weekend":    bool(dt.dayofweek >= 5),
        "season":        season,

        "demand_score":   score,
        "demand_label":   _demand_label(score),
        "base_score":     round(base_val, 2),
        "confidence_pct": confidence,

        **resources,

        "shap_top_factors": shap_contributions[:8],
        "shap_base_value":  round(base_val, 2),

        "inputs": {
            "temperature_c": temperature_c,
            "rainfall_mm":   rainfall_mm,
            "humidity_pct":  humidity_pct,
            "weather_suit":  weather_suit,
            "is_holiday":    bool(is_holiday),
            "is_event":      bool(is_event),
        },

        "model_info": {
            "model_name":    metadata["model_name"],
            "model_version": metadata["model_version"],
            "trained_at":    metadata["trained_at"],
            "test_mae":      metadata["metrics"]["test"]["mae"],
            "test_rmse":     metadata["metrics"]["test"]["rmse"],
            "test_mape":     metadata["metrics"]["test"]["mape"],
            "test_r2":       metadata["metrics"]["test"]["r2"],
        },
    }


def forecast_horizon(
    city:          str,
    place_name:    str,
    category:      str,
    avg_rating:    float,
    entry_fee_inr: float,
    weather_forecasts:   list[dict],
    holidays_map:        dict[str, str],
    events_map:          dict[str, str],
    last_demand_scores:  list[float],
    last_crowd_numerics: list[float],
    horizon_days: int = 7,
) -> dict:
    """
    Multi-day forecast used by the Forecast page (7/15/30-day).
    Rolls lag features forward with each predicted day.
    """
    dem_hist  = list(last_demand_scores[-7:])  if last_demand_scores  else [70.0] * 7
    crd_hist  = list(last_crowd_numerics[-1:]) if last_crowd_numerics else [2.0]
    forecasts = []

    for i in range(min(horizon_days, len(weather_forecasts))):
        w    = weather_forecasts[i]
        date = w["date"]

        lag1  = dem_hist[-1]
        lag7  = dem_hist[-7] if len(dem_hist) >= 7 else lag1
        roll  = round(sum(dem_hist[-7:]) / len(dem_hist[-7:]), 2)
        l1c   = crd_hist[-1]

        result = predict_demand(
            city=city, place_name=place_name, category=category,
            forecast_date=date,
            temperature_c  = w.get("temperature_c",           28.0),
            rainfall_mm    = w.get("rainfall_mm",              2.0),
            humidity_pct   = w.get("humidity_pct",            65.0),
            weather_suit   = w.get("weather_suitability_score", 0.65),
            is_holiday     = 1 if date in holidays_map else 0,
            is_event       = 1 if date in events_map   else 0,
            lag_1_demand   = lag1,
            lag_7_demand   = lag7,
            rolling_avg_7  = roll,
            lag_1_crowd    = l1c,
            avg_rating     = avg_rating,
            entry_fee_inr  = entry_fee_inr,
        )

        forecasts.append({
            "date":                   date,
            "day_of_week":            result["day_of_week"],
            "is_weekend":             result["is_weekend"],
            "is_holiday":             bool(date in holidays_map),
            "holiday_name":           holidays_map.get(date, ""),
            "is_event":               bool(date in events_map),
            "event_name":             events_map.get(date, ""),
            "demand_score":           result["demand_score"],
            "demand_label":           result["demand_label"],
            "hotel_occupancy_pct":    result["hotel_occupancy_pct"],
            "transport_demand_index": result["transport_demand_index"],
            "confidence_pct":         result["confidence_pct"],
            "top_factor":             result["shap_top_factors"][0]["feature"]
                                      if result["shap_top_factors"] else "",
            "temperature_c":          w.get("temperature_c", 28.0),
            "weather_condition":      w.get("weather_condition", "Sunny"),
        })

        dem_hist.append(result["demand_score"])

    if not forecasts:
        return {"city": city, "place_name": place_name,
                "horizon_days": horizon_days, "forecasts": [],
                "generated_at": datetime.now().isoformat(), "summary": {}}

    scores = [f["demand_score"] for f in forecasts]
    peak   = max(forecasts, key=lambda x: x["demand_score"])
    trough = min(forecasts, key=lambda x: x["demand_score"])

    return {
        "city":         city,
        "place_name":   place_name,
        "horizon_days": horizon_days,
        "generated_at": datetime.now().isoformat(),
        "forecasts":    forecasts,
        "summary": {
            "avg_demand_score":    round(sum(scores) / len(scores), 1),
            "peak_demand_score":   peak["demand_score"],
            "peak_date":           peak["date"],
            "trough_demand_score": trough["demand_score"],
            "trough_date":         trough["date"],
            "avg_hotel_occupancy": round(
                sum(f["hotel_occupancy_pct"] for f in forecasts) / len(forecasts), 1),
            "avg_transport_index": round(
                sum(f["transport_demand_index"] for f in forecasts) / len(forecasts), 1),
            "holiday_count": sum(1 for f in forecasts if f["is_holiday"]),
            "event_count":   sum(1 for f in forecasts if f["is_event"]),
        },
    }
