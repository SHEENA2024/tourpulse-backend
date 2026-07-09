"""
Loads all ML artifacts ONCE at FastAPI startup.
Every request uses the same in-memory objects — no per-request disk reads.
"""
import json
import joblib
import logging
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelStore:
    """Singleton that holds all loaded ML artifacts."""

    def __init__(self):
        self.model = None
        self.label_encoders = None
        self.shap_explainer = None
        self.metadata = None
        self.is_loaded = False

    def load(self):
        models_dir = Path(settings.models_dir)

        required = [
            "best_model.pkl",
            "label_encoders.pkl",
            "shap_explainer.pkl",
            "model_metadata.json",
        ]
        for fname in required:
            path = models_dir / fname
            if not path.exists():
                raise FileNotFoundError(
                    f"Missing model artifact: {path}\n"
                    f"Copy your models/ folder from Google Drive to {models_dir.resolve()}"
                )

        logger.info("Loading ML artifacts from %s ...", models_dir)

        self.model = joblib.load(models_dir / "best_model.pkl")
        logger.info("  ✅ best_model.pkl loaded")

        self.label_encoders = joblib.load(models_dir / "label_encoders.pkl")
        logger.info("  ✅ label_encoders.pkl loaded")

        try:
            self.shap_explainer = joblib.load(models_dir / "shap_explainer.pkl")
            logger.info("  ✅ shap_explainer.pkl loaded")
        except Exception as e:
            self.shap_explainer = None
            logger.warning("⚠️ Could not load shap_explainer.pkl: %s", e)
            logger.warning("Forecasts will continue without SHAP explanations.")

        with open(models_dir / "model_metadata.json") as f:
            self.metadata = json.load(f)
        logger.info("  ✅ model_metadata.json loaded")

        self.is_loaded = True
        logger.info("🚀 All ML artifacts ready")

    def reload(self):
        """Called after retraining to hot-swap the model without restarting."""
        logger.info("🔄 Reloading ML artifacts...")
        self.is_loaded = False
        self.load()


# Global singleton — imported by all services
model_store = ModelStore()
