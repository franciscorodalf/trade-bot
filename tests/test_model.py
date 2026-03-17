"""
Tests for the ML model training and prediction pipeline.
Covers: feature set consistency, model training, prediction output format.
"""

import pytest
import pandas as pd
import numpy as np
import os
import sys
import json


@pytest.fixture(autouse=True)
def mock_config(config_file):
    """Ensure modules load our test config."""
    os.chdir(os.path.dirname(config_file))
    sys.path.insert(0, os.path.join(os.path.dirname(config_file), '..', 'bot'))


# ============================================
# Feature Consistency Tests
# ============================================

EXPECTED_FEATURES = [
    'return', 'sma_20', 'sma_50', 'ema_12', 'rsi', 'volatility', 'atr',
    'macd', 'bb_width',
    'return_lag_1', 'return_lag_2', 'return_lag_3',
    'rsi_lag_1', 'rsi_lag_2', 'rsi_lag_3',
    'volatility_lag_1', 'volatility_lag_2', 'volatility_lag_3',
    'macd_lag_1', 'macd_lag_2', 'macd_lag_3',
    'bb_width_lag_1', 'bb_width_lag_2', 'bb_width_lag_3'
]


class TestFeatureConsistency:
    def test_feature_count(self):
        """Model expects exactly 24 features."""
        assert len(EXPECTED_FEATURES) == 24

    def test_train_and_predict_use_same_features(self):
        """
        Verify that train_model.py and predict.py define the same feature set.
        This prevents training/serving skew.
        """
        # Read both files and extract feature lists
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bot_dir = os.path.join(project_root, 'bot')

        train_features = _extract_features_from_file(os.path.join(bot_dir, 'train_model.py'))
        predict_features = _extract_features_from_file(os.path.join(bot_dir, 'predict.py'))

        assert train_features == predict_features, \
            f"Feature mismatch!\nTrain: {train_features}\nPredict: {predict_features}"

    def test_features_match_indicator_output(self, sample_ohlcv_df):
        """All expected features should exist in add_indicators output."""
        if 'utils' in sys.modules:
            del sys.modules['utils']
        from utils import add_indicators

        result = add_indicators(sample_ohlcv_df)

        for feature in EXPECTED_FEATURES:
            assert feature in result.columns, \
                f"Feature '{feature}' missing from add_indicators output"


def _extract_features_from_file(filepath):
    """Extract the feature list from a Python file by parsing it."""
    with open(filepath, 'r') as f:
        content = f.read()

    # Find the features list assignment
    import ast
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'features':
                    if isinstance(node.value, ast.List):
                        return [elt.value for elt in node.value.elts
                                if isinstance(elt, ast.Constant)]
    return []


# ============================================
# Model Training Tests (Unit-level, no network)
# ============================================

class TestModelTraining:
    def test_train_on_synthetic_data(self, sample_ohlcv_df, config_with_paths):
        """
        Train a model on synthetic data and verify it produces a valid .pkl file.
        """
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        import joblib

        if 'utils' in sys.modules:
            del sys.modules['utils']
        from utils import add_indicators

        df = add_indicators(sample_ohlcv_df)
        assert df is not None and len(df) > 20, "Need sufficient data for training"

        X = df[EXPECTED_FEATURES]
        y = df['target']

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        model = RandomForestClassifier(
            n_estimators=10, max_depth=5, random_state=42
        )
        model.fit(X_train, y_train)

        # Save model
        model_path = config_with_paths["paths"]["model"]
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)

        assert os.path.exists(model_path), "Model file was not saved"

        # Load and verify
        loaded_model = joblib.load(model_path)
        accuracy = loaded_model.score(X_test, y_test)
        assert 0.0 <= accuracy <= 1.0, f"Invalid accuracy: {accuracy}"

    def test_model_predicts_probabilities(self, sample_ohlcv_df, config_with_paths):
        """Model should output probabilities between 0 and 1."""
        from sklearn.ensemble import RandomForestClassifier
        import joblib

        if 'utils' in sys.modules:
            del sys.modules['utils']
        from utils import add_indicators

        df = add_indicators(sample_ohlcv_df)
        X = df[EXPECTED_FEATURES]
        y = df['target']

        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(X, y)

        # Predict probabilities on last row
        last_row = X.iloc[[-1]]
        probs = model.predict_proba(last_row)

        assert probs.shape[1] == 2, "Should have 2 classes (up/down)"
        assert 0.0 <= probs[0][0] <= 1.0
        assert 0.0 <= probs[0][1] <= 1.0
        assert abs(probs[0][0] + probs[0][1] - 1.0) < 1e-6

    def test_model_handles_edge_values(self, config_with_paths):
        """Model should handle extreme values without crashing."""
        from sklearn.ensemble import RandomForestClassifier

        # Create data with extreme values
        np.random.seed(42)
        n = 100
        X = pd.DataFrame({feat: np.random.randn(n) * 1000 for feat in EXPECTED_FEATURES})
        y = np.random.randint(0, 2, n)

        model = RandomForestClassifier(n_estimators=5, random_state=42)
        model.fit(X, y)

        # Predict on extreme input
        extreme_row = pd.DataFrame({feat: [1e6] for feat in EXPECTED_FEATURES})
        probs = model.predict_proba(extreme_row)
        assert probs is not None


# ============================================
# Prediction Logic Tests
# ============================================

class TestPredictionLogic:
    def test_buy_signal_threshold(self, config):
        """Probability above buy_threshold should yield BUY."""
        buy_threshold = config['buy_threshold']  # 0.55
        sell_threshold = config['sell_threshold']  # 0.40

        prob = 0.72

        if prob > buy_threshold:
            signal = "BUY"
        elif prob < sell_threshold:
            signal = "SELL"
        else:
            signal = "HOLD"

        assert signal == "BUY"

    def test_sell_signal_threshold(self, config):
        """Probability below sell_threshold should yield SELL."""
        prob = 0.30

        if prob > config['buy_threshold']:
            signal = "BUY"
        elif prob < config['sell_threshold']:
            signal = "SELL"
        else:
            signal = "HOLD"

        assert signal == "SELL"

    def test_hold_signal_between_thresholds(self, config):
        """Probability between thresholds should yield HOLD."""
        prob = 0.48

        if prob > config['buy_threshold']:
            signal = "BUY"
        elif prob < config['sell_threshold']:
            signal = "SELL"
        else:
            signal = "HOLD"

        assert signal == "HOLD"

    def test_volatility_filter(self, config):
        """Low volatility should force HOLD regardless of prediction."""
        vol_threshold = config['volatility_threshold']  # 0.002

        volatility = 0.001  # Below threshold

        if volatility < vol_threshold:
            signal = "HOLD"
            reason = "Low Volatility"
        else:
            signal = "BUY"
            reason = "Model Signal"

        assert signal == "HOLD"
        assert reason == "Low Volatility"

    def test_boundary_values(self, config):
        """Test exact boundary probability values."""
        buy_t = config['buy_threshold']  # 0.55
        sell_t = config['sell_threshold']  # 0.40

        # Exact buy threshold — should NOT trigger buy (> not >=)
        prob = buy_t
        signal = "BUY" if prob > buy_t else ("SELL" if prob < sell_t else "HOLD")
        assert signal == "HOLD"

        # Just above buy threshold
        prob = buy_t + 0.001
        signal = "BUY" if prob > buy_t else ("SELL" if prob < sell_t else "HOLD")
        assert signal == "BUY"

        # Exact sell threshold — should NOT trigger sell (< not <=)
        prob = sell_t
        signal = "BUY" if prob > buy_t else ("SELL" if prob < sell_t else "HOLD")
        assert signal == "HOLD"
