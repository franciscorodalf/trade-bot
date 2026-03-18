"""
Real-time prediction engine with calibrated probabilities.

Loads the trained XGBoost model, scaler, and isotonic calibrator
to generate calibrated UP/DOWN probabilities from live market features.
"""

import json
import logging
import os
from typing import Optional, Dict, Any

import joblib
import numpy as np
import pandas as pd

from features import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

with open("config.json", "r") as f:
    config = json.load(f)


class Predictor:
    """
    Generates calibrated probability predictions for BTC price direction.

    The prediction pipeline:
    1. Receive raw features from FeatureEngine
    2. Scale features using the trained scaler
    3. Run XGBoost inference → raw probability
    4. Calibrate via isotonic regression → calibrated probability
    5. Return signal with confidence and metadata
    """

    def __init__(self) -> None:
        self.model = None
        self.scaler = None
        self.calibrator = None
        self._loaded = False

    def load(self) -> bool:
        """Load model, scaler, and calibrator from disk."""
        paths = config["paths"]

        for name, path in [("model", paths["model"]),
                           ("scaler", paths["scaler"]),
                           ("calibrator", paths["calibrator"])]:
            if not os.path.exists(path):
                logger.error(f"{name} not found at {path}. Run train_model.py first.")
                return False

        self.model = joblib.load(paths["model"])
        self.scaler = joblib.load(paths["scaler"])
        self.calibrator = joblib.load(paths["calibrator"])
        self._loaded = True
        logger.info("Predictor loaded: model + scaler + calibrator")
        return True

    def predict(self, features: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """
        Generate a calibrated prediction from live features.

        Args:
            features: Dict of feature_name → value from FeatureEngine.

        Returns:
            Dict with:
                - signal: "UP" or "DOWN"
                - raw_probability: Uncalibrated model output
                - calibrated_probability: Isotonic-calibrated probability
                - confidence: How far from 50% (0 = no confidence, 0.5 = max)
                - features_used: Number of non-zero features
        """
        if not self._loaded:
            if not self.load():
                return None

        # Build feature vector in correct order
        feature_values = [features.get(col, 0.0) for col in FEATURE_COLUMNS]
        X = np.array([feature_values])

        # Handle NaN/inf
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # Scale
        X_scaled = self.scaler.transform(X)

        # Raw prediction
        raw_prob = float(self.model.predict_proba(X_scaled)[0][1])

        # Calibrate
        calibrated_prob = float(self.calibrator.predict([raw_prob])[0])

        # Signal
        signal = "UP" if calibrated_prob >= 0.5 else "DOWN"
        confidence = abs(calibrated_prob - 0.5)

        # Count non-zero features (data quality check)
        non_zero = sum(1 for v in feature_values if v != 0)

        result = {
            "signal": signal,
            "raw_probability": round(raw_prob, 4),
            "calibrated_probability": round(calibrated_prob, 4),
            "confidence": round(confidence, 4),
            "features_used": non_zero,
            "total_features": len(FEATURE_COLUMNS),
        }

        logger.info(
            f"Prediction: {signal} (cal={calibrated_prob:.3f}, "
            f"raw={raw_prob:.3f}, conf={confidence:.3f}, "
            f"features={non_zero}/{len(FEATURE_COLUMNS)})"
        )

        return result
