"""
MLOps monitoring endpoints.
GET  /api/mlops/status    — current model version, metrics, drift, last retrain
POST /api/mlops/retrain   — trigger manual retraining (placeholder for now)
GET  /api/mlops/drift     — run or fetch drift report
GET  /api/mlops/history   — retraining history
"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import DriftReport, RetrainLog
from app.core.model_loader import model_store
from app.core.config import settings
from app.services.drift import run_drift_check, get_latest_drift

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mlops", tags=["MLOps"])


def _require_admin(x_admin_key: str = Header(default=None)):
    if x_admin_key != settings.admin_secret_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")


# ── GET /api/mlops/status ─────────────────────────────────────────────────────
@router.get("/status")
def get_mlops_status(db: Session = Depends(get_db)):
    """Returns everything the MLOps monitoring dashboard card needs."""
    if not model_store.is_loaded:
        return {"error": "Model not loaded", "is_model_loaded": False}

    meta = model_store.metadata

    # Latest drift
    drift = get_latest_drift(db)

    # Latest retrain
    last_retrain = db.query(RetrainLog).order_by(
        RetrainLog.finished_at.desc()
    ).first()

    return {
        "is_model_loaded": True,

        # Model identity
        "model_name":    meta["model_name"],
        "model_version": meta["model_version"],
        "trained_at":    meta["trained_at"],

        # Performance metrics
        "test_mae":  meta["metrics"]["test"]["mae"],
        "test_rmse": meta["metrics"]["test"]["rmse"],
        "test_mape": meta["metrics"]["test"]["mape"],
        "test_r2":   meta["metrics"]["test"]["r2"],

        # All models comparison
        "model_comparison": {
            "xgboost":      meta["metrics"].get("xgb",  {}),
            "randomforest": meta["metrics"].get("rf",   {}),
            "lightgbm":     meta["metrics"].get("lgbm", {}),
        },

        # Drift
        "drift_status":    drift.get("status", "no_data"),
        "drift_score":     drift.get("drift_score"),
        "last_drift_check": drift.get("run_at"),

        # Retraining
        "last_retrain_at":  last_retrain.finished_at.isoformat() if last_retrain and last_retrain.finished_at else None,
        "last_retrain_by":  last_retrain.triggered_by if last_retrain else None,
        "last_retrain_outcome": last_retrain.outcome if last_retrain else None,

        # MLflow info
        "mlflow_experiment": meta.get("mlflow", {}).get("experiment"),
    }


# ── GET /api/mlops/drift ──────────────────────────────────────────────────────
@router.get("/drift")
def check_drift(db: Session = Depends(get_db)):
    """Runs a fresh drift check and returns the result."""
    result = run_drift_check(db)
    return result


# ── GET /api/mlops/drift/history ─────────────────────────────────────────────
@router.get("/drift/history")
def drift_history(limit: int = 10, db: Session = Depends(get_db)):
    rows = db.query(DriftReport).order_by(
        DriftReport.run_at.desc()
    ).limit(limit).all()

    return {
        "history": [
            {"id": r.id, "run_at": r.run_at.isoformat(),
             "drift_score": r.drift_score, "status": r.status}
            for r in rows
        ]
    }


# ── POST /api/mlops/retrain ───────────────────────────────────────────────────
@router.post("/retrain")
def trigger_retrain(
    db:    Session = Depends(get_db),
    _auth: None    = Depends(_require_admin),
):
    """
    Logs a manual retrain trigger.
    In production this would kick off a background Colab/Vertex job.
    For now, it logs the request and returns instructions.
    """
    log = RetrainLog(
        triggered_by="manual",
        started_at=datetime.utcnow(),
        outcome="pending",
        notes="Manual retrain triggered via API. Run the Jupyter notebook to retrain.",
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return {
        "status": "triggered",
        "log_id": log.id,
        "message": (
            "Retrain logged. To retrain: open TourPulse_ML_Pipeline.ipynb, "
            "call reset_all_checkpoints(), run all cells, then copy the new "
            "models/ folder to the backend and restart."
        ),
    }


# ── GET /api/mlops/history ────────────────────────────────────────────────────
@router.get("/history")
def retrain_history(limit: int = 10, db: Session = Depends(get_db)):
    rows = db.query(RetrainLog).order_by(
        RetrainLog.started_at.desc()
    ).limit(limit).all()

    return {
        "history": [
            {
                "id":           r.id,
                "triggered_by": r.triggered_by,
                "started_at":   r.started_at.isoformat() if r.started_at else None,
                "finished_at":  r.finished_at.isoformat() if r.finished_at else None,
                "outcome":      r.outcome,
                "old_mae":      r.old_mae,
                "new_mae":      r.new_mae,
                "notes":        r.notes,
            }
            for r in rows
        ]
    }
