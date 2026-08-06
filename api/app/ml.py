"""ML model wrapper: loads the trained XGBoost artifacts and predicts delays."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .config import settings

log = logging.getLogger("citypulse.ml")

BUCKET_NAMES = {0: "on_time", 1: "delayed", 2: "severe"}


class DelayModel:
    def __init__(self, model_path: str | None = None, features_path: str | None = None):
        self.loaded = False
        self.error: str | None = None
        self.model_path = model_path or settings()["ml_model_path"]
        self.features_path = features_path or settings()["ml_features_path"]
        self._load()

    def _load(self) -> None:
        mp, fp = Path(self.model_path), Path(self.features_path)
        # fall back to repo-local artifacts when running without Docker
        if not mp.exists():
            local = Path(__file__).resolve().parents[2] / "ml/model/model.joblib"
            if local.exists():
                mp, fp = local, local.with_name("features.json")
        if not mp.exists():
            self.error = f"model not found at {self.model_path}"
            log.warning(self.error)
            return
        try:
            self.artifacts = joblib.load(mp)
            self.features = json.loads(fp.read_text())
            self.loaded = True
        except Exception as e:  # noqa: BLE001
            self.error = f"failed to load model: {e}"
            log.error(self.error)

    def info(self) -> dict:
        return {
            "loaded": self.loaded,
            "error": self.error,
            "model_path": self.model_path,
            "features": self.features if self.loaded else None,
        }

    def predict(self, features: dict) -> dict:
        if not self.loaded:
            return {"loaded": False, "error": self.error or "model unavailable"}
        cat = self.features.get("cat_features", [])
        num = self.features.get("num_features", [])
        row = {}
        for col in cat:
            row[col] = str(features.get(col, "unknown"))
        for col in num:
            try:
                row[col] = float(features.get(col, 0.0))
            except (TypeError, ValueError):
                row[col] = 0.0
        df = pd.DataFrame([row])
        regressor = self.artifacts["regressor"]
        classifier = self.artifacts["classifier"]
        delay_pred = float(np.clip(regressor.predict(df)[0], 0, 1800))
        probs = classifier.predict_proba(df)[0]
        bucket_id = int(classifier.predict(df)[0])
        names = {int(k): v for k, v in self.features.get("bucket_names", BUCKET_NAMES).items()}
        return {
            "loaded": True,
            "predicted_delay_seconds": round(delay_pred, 1),
            "predicted_bucket": names.get(bucket_id, "on_time"),
            "probabilities": {names.get(i, str(i)): round(float(p), 4) for i, p in enumerate(probs)},
            "features_used": {**{c: row[c] for c in cat}, **{c: row[c] for c in num}},
        }


model = DelayModel()
