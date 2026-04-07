"""
Robust inference wrapper for NIDS demo.

- Ensures features align with trained scaler order.
- Handles SHAP explainability safely.
- Prevents array truth ambiguity errors.
- Compatible with ensemble (RF + ISO) detector.
"""

import os
import time
import joblib
import numpy as np
import pandas as pd
import traceback
import warnings
from feature_extraction import FEATURE_KEYS, row_to_vector

# Suppress SHAP warnings
warnings.filterwarnings("ignore", message="Please use inner_full rather than model_output")

MODELS_DIR = os.path.join(os.path.dirname(__file__), 'models')


class EnsembleDetector:
    def __init__(self, alpha=0.6, beta=0.4, thresh=0.5):
        self.alpha = alpha
        self.beta = beta
        self.thresh = thresh
        self.scaler = None
        self.rf = None
        self.iso = None
        self.explainer = None
        self.expected_features = None
        self._load()

    # ===============================================================
    # Load Models
    # ===============================================================
    def _load(self):
        """Load scaler, models, and SHAP explainer."""
        try:
            self.scaler = joblib.load(os.path.join(MODELS_DIR, 'scaler.joblib'))
            self.rf = joblib.load(os.path.join(MODELS_DIR, 'supervised_rf.joblib'))
            self.iso = joblib.load(os.path.join(MODELS_DIR, 'unsupervised_iso.joblib'))
            print("[INFO] Models loaded successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to load model files: {e}")
            raise

        try:
            self.explainer = joblib.load(os.path.join(MODELS_DIR, 'shap_explainer.joblib'))
            print("[INFO] SHAP explainer loaded.")
        except Exception as e:
            print(f"[WARN] SHAP explainer not found: {e}. Explainability disabled.")
            self.explainer = None

        if hasattr(self.scaler, 'n_features_in_'):
            self.expected_features = self.scaler.n_features_in_
        else:
            self.expected_features = len(FEATURE_KEYS)
            print("[WARN] Scaler missing 'n_features_in_'; using fallback.")

        print(f"[INFO] Scaler expects {self.expected_features} features.")

    # ===============================================================
    # Feature Preparation
    # ===============================================================
    def _prepare_vector(self, flow_row: dict):
        """Convert a flow dict to a scaled and correctly ordered vector."""
        vec = row_to_vector(flow_row)

        if vec.shape[1] != self.expected_features:
            print(f"[WARN] Feature mismatch: input has {vec.shape[1]}, expected {self.expected_features}.")
            aligned_vec = np.zeros((1, self.expected_features))
            aligned_vec[0, :min(vec.shape[1], self.expected_features)] = vec[0, :min(vec.shape[1], self.expected_features)]
            vec = aligned_vec

        return vec

    # ===============================================================
    # Prediction Logic
    # ===============================================================
    def predict(self, flow_row: dict):
        """Predict a single flow with combined supervised + unsupervised models."""
        start_time = time.time()

        try:
            raw_vec = self._prepare_vector(flow_row)
            raw_df = pd.DataFrame(raw_vec, columns=FEATURE_KEYS)

            # Align order with the scaler used during training
            if hasattr(self.scaler, 'feature_names_in_'):
                correct_order = self.scaler.feature_names_in_
                try:
                    raw_df = raw_df[correct_order]
                except KeyError as e:
                    print(f"[ERROR] Feature mismatch: {e}")
                    return {'error': 'Critical feature mismatch', 'latency_ms': 0}
            else:
                print("[WARN] Scaler missing 'feature_names_in_'; cannot verify column order.")

            scaled_vec = self.scaler.transform(raw_df)

            # Supervised and unsupervised predictions
            supervised_prob = self.rf.predict_proba(scaled_vec)[0, 1]
            unsupervised_score = self.iso.score_samples(scaled_vec)[0]
            unsupervised_prob = np.interp(unsupervised_score, [-1.0, 0.0], [1.0, 0.0])

            attack_score = (self.alpha * supervised_prob) + (self.beta * unsupervised_prob)
            label = 1 if attack_score >= self.thresh else 0

            latency_ms = (time.time() - start_time) * 1000

            result = {
                'supervised_prob': float(supervised_prob),
                'unsupervised_score': float(unsupervised_prob),
                'attack_score': float(attack_score),
                'label': int(label),
                'latency_ms': float(latency_ms),
                'shap_explain': {}
            }

            # SHAP explainability (safe mode)
            if label == 1 and self.explainer:
                try:
                    shap_values_raw = self.explainer.shap_values(scaled_vec)

                    # Normalize all possible SHAP output structures
                    if isinstance(shap_values_raw, list):
                        shap_values = shap_values_raw[-1]
                    elif isinstance(shap_values_raw, np.ndarray):
                        shap_values = shap_values_raw
                    else:
                        shap_values = np.array(shap_values_raw)

                    if shap_values.ndim > 1:
                        shap_values = shap_values[0]

                    if hasattr(self.scaler, 'feature_names_in_'):
                        feature_names = self.scaler.feature_names_in_
                    else:
                        feature_names = FEATURE_KEYS

                    shap_dict = dict(zip(feature_names, shap_values))
                    top_features = sorted(shap_dict.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
                    result['shap_explain'] = dict(top_features)
                except Exception as e:
                    print(f"[WARN] Simplified SHAP explanation failed: {e}")
                    result['shap_explain'] = {}

            return result

        except Exception as e:
            print(f"[ERROR] predict() failed: {e}")
            traceback.print_exc()
            return {
                'error': str(e),
                'traceback': traceback.format_exc(),
                'latency_ms': (time.time() - start_time) * 1000
            }

    # ===============================================================
    # Parameter Update
    # ===============================================================
    def set_params(self, alpha=None, beta=None, thresh=None):
        """Adjust blending and threshold parameters dynamically."""
        try:
            if alpha is not None:
                self.alpha = float(alpha)
            if beta is not None:
                self.beta = float(beta)
            if thresh is not None:
                self.thresh = float(thresh)
            print(f"[INFO] Detector parameters updated: α={self.alpha}, β={self.beta}, T={self.thresh}")
        except Exception as e:
            print(f"[ERROR] Failed to set parameters: {e}")


# ===============================================================
# Public API
# ===============================================================
_detector = EnsembleDetector()


def predict_flow(flow_row: dict):
    return _detector.predict(flow_row)


def set_detector_params(alpha=None, beta=None, thresh=None):
    _detector.set_params(alpha, beta, thresh)


def get_detector_info():
    return {
        'alpha': _detector.alpha,
        'beta': _detector.beta,
        'thresh': _detector.thresh,
        'scaler_expected_features': _detector.expected_features,
        'feature_keys_len': len(FEATURE_KEYS),
        'feature_keys': FEATURE_KEYS
    }
