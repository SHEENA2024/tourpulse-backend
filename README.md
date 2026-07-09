# TourPulse Backend

FastAPI backend for the TourPulse tourism demand forecasting platform.

## Quick Start

### 1. Copy model artifacts
See `models/README.md` for instructions on copying files from Google Drive.

### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env — set MODELS_DIR, FRONTEND_URL, ADMIN_SECRET_KEY
```

### 4. Run the server
```bash
uvicorn app.main:app --reload --port 8000
```

Visit http://localhost:8000/docs for the interactive API explorer.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check + model status |
| GET | `/api/places` | All cities and places |
| GET | `/api/forecast/{city}/{place_name}?horizon=7` | Multi-day forecast |
| GET | `/api/heatmap?target_date=YYYY-MM-DD` | All places demand for a date |
| GET | `/api/mlops/status` | Model version, metrics, drift status |
| GET | `/api/mlops/drift` | Run drift check |
| GET | `/api/mlops/drift/history` | Past drift reports |
| POST | `/api/mlops/retrain` | Trigger manual retrain (admin) |
| GET | `/api/mlops/history` | Retraining history |
| GET | `/api/admin/events` | List events |
| POST | `/api/admin/events` | Add event (admin) |
| PUT | `/api/admin/events/{id}` | Update event (admin) |
| DELETE | `/api/admin/events/{id}` | Delete event (admin) |
| GET | `/api/admin/holidays` | List holidays |
| POST | `/api/admin/holidays` | Add holiday (admin) |
| DELETE | `/api/admin/holidays/{id}` | Delete holiday (admin) |

Admin endpoints require header: `X-Admin-Key: your-secret-key`

---

## Project Structure

```
tourpulse-backend/
├── app/
│   ├── main.py              ← FastAPI app, CORS, startup, scheduler
│   ├── api/
│   │   ├── forecast.py      ← /api/forecast, /api/heatmap, /api/places
│   │   ├── mlops.py         ← /api/mlops/*
│   │   ├── admin.py         ← /api/admin/*
│   │   └── health.py        ← /health
│   ├── core/
│   │   ├── config.py        ← Settings from .env
│   │   └── model_loader.py  ← Loads ML artifacts once at startup
│   ├── db/
│   │   ├── database.py      ← SQLAlchemy setup
│   │   └── models.py        ← ORM models (Events, Holidays, Drift, Retrain)
│   ├── schemas/
│   │   ├── forecast.py      ← Pydantic response models
│   │   └── admin.py         ← Pydantic request/response models
│   └── services/
│       ├── predictor.py     ← predict_demand() + forecast_horizon()
│       ├── weather.py       ← Open-Meteo API + SQLite cache
│       ├── holidays.py      ← Indian holidays + DB events lookup
│       └── drift.py         ← Evidently AI drift detection
├── models/                  ← Place your .pkl files here
├── requirements.txt
├── .env.example
└── README.md
```

---

## Deployment (Render)

1. Push this folder to GitHub
2. Create a new Render Web Service
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables from `.env.example`
6. Upload model files to Render disk or use persistent storage
