from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Paths
    models_dir: str = "./models/models-1/models"
    database_url: str = "sqlite:///./tourpulse.db"

    # CORS
    frontend_url: str = "http://localhost:5173"

    # Security
    admin_secret_key: str = "tourpulse-admin-secret"

    # Drift thresholds
    drift_mae_threshold: float = 18.0
    drift_score_threshold: float = 0.25

    # Features (must match notebook FEATURES_ENC exactly)
    feature_names: list[str] = [
        "visit_month", "week_of_year", "day_of_week_num", "is_weekend",
        "temperature_c", "rainfall_mm", "humidity_percent",
        "weather_suitability_score", "is_holiday", "is_event",
        "lag_1_demand", "lag_7_demand", "rolling_avg_7_demand",
        "lag_1_crowd", "avg_rating", "entry_fee_inr",
        "city_enc", "category_enc", "season_enc",
    ]

    # City resource planning multipliers (occupancy_factor, transport_factor)
    city_factors: dict = {
        "Ooty": [0.85, 0.75], "Manali": [0.90, 0.70],
        "Gulmarg": [0.88, 0.65], "Srinagar": [0.82, 0.72],
        "Jaipur": [0.78, 0.80], "Agra": [0.80, 0.82],
        "Delhi": [0.70, 0.90], "Mumbai": [0.72, 0.92],
        "Kolkata": [0.68, 0.88], "Hyderabad": [0.74, 0.85],
        "Mysore": [0.76, 0.78], "Alleppey": [0.83, 0.70],
        "Madurai": [0.77, 0.76], "Varanasi": [0.79, 0.73],
        "Amritsar": [0.81, 0.77],
    }

    # Auto retraining
    auto_retrain_enabled: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
