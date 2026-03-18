"""Tests for the prediction and model modules."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))

import numpy as np
from features import FEATURE_COLUMNS


class TestFeatureConsistency:
    def test_feature_columns_are_strings(self):
        assert all(isinstance(f, str) for f in FEATURE_COLUMNS)

    def test_feature_columns_not_empty(self):
        assert len(FEATURE_COLUMNS) > 0

    def test_no_target_in_features(self):
        """Target should never be in feature columns."""
        assert "target" not in FEATURE_COLUMNS

    def test_no_timestamp_in_features(self):
        """Timestamp should never be a feature."""
        assert "timestamp" not in FEATURE_COLUMNS


class TestSampleFeatures:
    def test_all_features_present(self, sample_features):
        """Sample features fixture should have all required columns."""
        for col in FEATURE_COLUMNS:
            assert col in sample_features, f"Missing feature: {col}"

    def test_features_are_numeric(self, sample_features):
        """All feature values should be numeric."""
        for col in FEATURE_COLUMNS:
            val = sample_features[col]
            assert isinstance(val, (int, float)), f"{col} is {type(val)}"
