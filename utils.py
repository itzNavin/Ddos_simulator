# backend/utils.py

import os
import joblib
from typing import Dict, List, Tuple

# Directory where your trained models live
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

# Load models on import
try:
    _xgb_model = joblib.load(os.path.join(MODEL_DIR, "xgb_model.pkl"))
    _iso_model = joblib.load(os.path.join(MODEL_DIR, "iso_50.pkl"))
    # Determine how many features the XGBoost model expects
    _xgb_feature_count = getattr(_xgb_model, "n_features_in_", None)
except Exception as e:
    raise RuntimeError(f"Failed to load models: {e}")

# Define the basic keys we generate in simulation
FEATURE_KEYS = ["duration", "protocol_type", "src_bytes", "dst_bytes"]
PROTOCOL_MAP = {"tcp": 0, "udp": 1, "icmp": 2}


def extract_features(sim_data: Dict[str, float]) -> List[float]:
    """
    Convert sim_data dict into numeric feature list.
    sim_data should contain keys: duration, protocol_type, src_bytes, dst_bytes
    """
    try:
        return [
            float(sim_data["duration"]),
            PROTOCOL_MAP.get(sim_data["protocol_type"], 0),
            float(sim_data["src_bytes"]),
            float(sim_data["dst_bytes"]),
        ]
    except KeyError as e:
        raise ValueError(f"Missing feature key: {e}")
    except Exception as e:
        raise ValueError(f"Error extracting features: {e}")


def classify(features: List[float]) -> Tuple[int, float]:
    """
    Predict label (0=normal,1=ddos) and anomaly score.
    Pads or truncates the feature vector to match the model's expected input length.
    """
    if not isinstance(features, (list, tuple)):
        raise TypeError("Features must be a list or tuple of numeric values")

    # If the model expects more features than provided, pad with zeros.
    if _xgb_feature_count is not None and len(features) != _xgb_feature_count:
        diff = _xgb_feature_count - len(features)
        if diff > 0:
            features = features + [0.0] * diff
        else:
            features = features[:_xgb_feature_count]

    try:
        # XGBoost classification prediction
        pred = int(_xgb_model.predict([features])[0])
        # Isolation Forest anomaly score
        score = float(_iso_model.decision_function([features])[0])
        return pred, score
    except Exception as e:
        raise RuntimeError(f"Classification error: {e}")
