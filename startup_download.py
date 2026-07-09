import os, sys
from pathlib import Path

HF_REPO_ID = os.environ.get("HF_REPO_ID", "")
MODELS_DIR = Path(os.environ.get("MODELS_DIR", "./models"))
REQUIRED = ["best_model.pkl", "label_encoders.pkl", "shap_explainer.pkl",
            "model_metadata.json", "reference_dataset.csv"]


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    missing = [f for f in REQUIRED if not (MODELS_DIR / f).exists()]
    if not missing:
        print("✅ All model artifacts already present")
        return
    if not HF_REPO_ID:
        print("⚠️ HF_REPO_ID not set — skipping")
        return
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        os.system(f"{sys.executable} -m pip install huggingface_hub -q")
        from huggingface_hub import hf_hub_download
    print(f"📥 Downloading from {HF_REPO_ID}...")
    for fname in missing:
        print(f"  ⬇ {fname}...", end=" ", flush=True)
        try:
            hf_hub_download(repo_id=HF_REPO_ID, filename=fname,
                           repo_type="model", local_dir=str(MODELS_DIR))
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            sys.exit(1)
    print("🚀 All artifacts ready")


if __name__ == "__main__":
    main()
