from fastapi import APIRouter
from app.core.model_loader import model_store

router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    return {
        "status":         "ok",
        "model_loaded":   model_store.is_loaded,
        "model_name":     model_store.metadata["model_name"] if model_store.is_loaded else None,
        "model_version":  model_store.metadata["model_version"] if model_store.is_loaded else None,
    }
