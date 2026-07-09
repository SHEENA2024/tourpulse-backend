"""
Drift detection using Evidently AI.
Compares the training reference distribution against recent predictions
to flag when the model's input distribution has shifted.
"""
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.models import DriftReport

logger = logging.getLogger(__name__)


def run_drift_check(db: Session) -> dict:
    """
    Loads reference dataset, compares against recent cached weather inputs,
    computes drift score, saves a DriftReport to DB.
    Returns a summary dict.
    """
    try:
        from evidently.report import Report
        from evidently.metric_preset import DataDriftPreset
        from evidently.metrics import DatasetDriftMetric
    except ImportError:
        logger.warning("Evidently not installed — skipping drift check")
        return {"status": "skipped", "reason": "evidently not installed"}

    models_dir   = Path(settings.models_dir)
    ref_csv      = models_dir / "reference_dataset.csv"

    if not ref_csv.exists():
        logger.warning("reference_dataset.csv not found — skipping drift check")
        return {"status": "skipped", "reason": "reference_dataset.csv missing"}

    # Load reference
    reference = pd.read_csv(ref_csv)

    # Build a "current" snapshot from weather cache
    from app.db.models import WeatherCache
    from app.db.database import SessionLocal

    cache_rows = db.query(WeatherCache).order_by(
        WeatherCache.fetched_at.desc()
    ).limit(200).all()

    if len(cache_rows) < 30:
        logger.info("Not enough recent data for drift check (%d rows)", len(cache_rows))
        return {"status": "skipped", "reason": f"only {len(cache_rows)} recent rows (need 30+)"}

    # Build a current dataframe with the same numeric feature columns
    numeric_features = [
        "temperature_c", "rainfall_mm", "humidity_percent",
        "weather_suitability_score", "is_holiday", "is_event",
        "avg_rating", "demand_score",
    ]

    current_data = pd.DataFrame([{
        "temperature_c":           r.temperature_c or 28.0,
        "rainfall_mm":             r.rainfall_mm or 2.0,
        "humidity_percent":        r.humidity_pct or 65.0,
        "weather_suitability_score": r.weather_suitability or 0.65,
        "is_holiday":              0,
        "is_event":                0,
        "avg_rating":              4.0,
        "demand_score":            70.0,   # placeholder; real scores logged separately
    } for r in cache_rows])

    ref_subset = reference[[c for c in numeric_features if c in reference.columns]].dropna()

    # Run Evidently report
    report = Report(metrics=[DatasetDriftMetric()])
    report.run(reference_data=ref_subset, current_data=current_data)
    result = report.as_dict()

    drift_detected = result["metrics"][0]["result"]["dataset_drift"]
    drift_score    = round(result["metrics"][0]["result"]["share_of_drifted_columns"], 4)

    if drift_detected:
        status = "critical" if drift_score > settings.drift_score_threshold else "warning"
    else:
        status = "ok"

    details = json.dumps({
        "drift_detected": drift_detected,
        "drift_score":    drift_score,
        "n_reference":    len(ref_subset),
        "n_current":      len(current_data),
    })

    # Save to DB
    report_row = DriftReport(
        run_at=datetime.utcnow(),
        drift_score=drift_score,
        status=status,
        details=details,
    )
    db.add(report_row)
    db.commit()

    logger.info("Drift check done — status=%s  score=%.3f", status, drift_score)
    return {"status": status, "drift_score": drift_score, "details": details}


def get_latest_drift(db: Session) -> dict:
    """Returns the most recent drift report from DB."""
    row = db.query(DriftReport).order_by(DriftReport.run_at.desc()).first()
    if not row:
        return {"status": "no_data", "drift_score": None, "run_at": None}
    return {
        "status":      row.status,
        "drift_score": row.drift_score,
        "run_at":      row.run_at.isoformat() if row.run_at else None,
        "details":     json.loads(row.details) if row.details else {},
    }
