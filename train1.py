#!/usr/bin/env python3
import os
import argparse
import json
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_curve,
    precision_recall_curve
)
import joblib

# Optional SHAP
try:
    import shap
except ImportError:
    shap = None

# ===============================================================
# CONFIG
# ===============================================================
PROTO_MAP = {'tcp': 0, 'udp': 1, 'icmp': 2, 'others': 3}

FEATURE_KEYS = [
    'Protocol', 'Flow Duration', 'Total Fwd Packets', 'Total Backward Packets',
    'Total Length of Fwd Packets', 'Total Length of Bwd Packets',
    'Fwd Packet Length Mean', 'Bwd Packet Length Mean',
    'Flow IAT Mean', 'Fwd IAT Mean', 'Bwd IAT Mean',
    'Fwd PSH Flags', 'Bwd PSH Flags', 'Fwd URG Flags', 'Bwd URG Flags'
]

LABEL_COL = 'Label'

# ===============================================================
# HELPERS
# ===============================================================
def encode_protocol(proto_value):
    if pd.isna(proto_value):
        return 3.0
    val = str(proto_value).lower()
    return float(PROTO_MAP.get(val, 3))

def preprocess_dataframe(df):
    print(f"[INFO] Original columns: {len(df.columns)}")
    df.columns = df.columns.str.strip()
    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    missing_cols = [col for col in FEATURE_KEYS if col not in df.columns]
    if missing_cols:
        print(f"[WARN] Missing required feature columns: {missing_cols}")
        for col in missing_cols:
            df[col] = 0.0

    if LABEL_COL not in df.columns:
        raise ValueError(f"Label column '{LABEL_COL}' not found in CSV.")

    df[FEATURE_KEYS] = df[FEATURE_KEYS].fillna(0.0)

    # Encode protocol if string/object
    if 'Protocol' in df.columns:
        if df['Protocol'].dtype == 'object' or pd.api.types.is_string_dtype(df['Protocol']):
            df['Protocol'] = df['Protocol'].apply(encode_protocol)
        else:
            df['Protocol'] = df['Protocol'].map({6:0, 17:1, 1:2}).fillna(3)

    print("[INFO] Encoding 'Label' column...")
    y = df[LABEL_COL].apply(lambda x: 0 if str(x).strip().upper() in ('BENIGN','NORMAL','0') else 1)

    X = df[FEATURE_KEYS].astype(np.float64)
    print(f"[INFO] Preprocessing complete. X shape: {X.shape}, y labels: {len(y)}")
    return X, y

# ===============================================================
# MAIN FUNCTION
# ===============================================================
def main(csv_path):
    print(f"[INFO] Loading CSV: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"[ERROR] Could not read CSV: {e}")
        return

    X, y = preprocess_dataframe(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    print(f"[INFO] Data split: Train={len(y_train)}, Test={len(y_test)}")

    # ===========================================================
    # TRAIN MODELS
    # ===========================================================
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    print("[INFO] Training RandomForestClassifier...")
    rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X_train_scaled, y_train)

    print("[INFO] Training IsolationForest (unsupervised)...")
    iso = IsolationForest(n_estimators=100, contamination=0.1, random_state=42, n_jobs=-1)
    iso.fit(X_train_scaled)

    # ===========================================================
    # SHAP EXPLAINER (Optional)
    # ===========================================================
    explainer = None
    if shap is not None:
        try:
            explainer = shap.TreeExplainer(rf)
            print("[INFO] SHAP explainer created successfully.")
        except Exception as e:
            print(f"[WARN] Could not create SHAP explainer: {e}")
    else:
        print("[INFO] SHAP not installed — skipping feature explainability.")

    # ===========================================================
    # EVALUATION
    # ===========================================================
    print("[INFO] Evaluating model...")
    y_pred = rf.predict(X_test_scaled)

    try:
        y_score = rf.predict_proba(X_test_scaled)[:, 1]
    except Exception:
        y_score = None

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    cm_arr = confusion_matrix(y_test, y_pred).tolist()

    print(f"\n[RESULT] Accuracy: {acc * 100:.2f}%")
    print(f"[RESULT] Precision: {prec:.4f}")
    print(f"[RESULT] Recall: {rec:.4f}")
    print(f"[RESULT] F1 Score: {f1:.4f}")
    print("\n[RESULT] Classification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))

    # ===========================================================
    # CURVE DATA
    # ===========================================================
    roc_data, pr_data = {}, {}
    if y_score is not None:
        try:
            fpr, tpr, _ = roc_curve(y_test, y_score)
            precision_curve, recall_curve, _ = precision_recall_curve(y_test, y_score)
            roc_data = {"fpr": fpr.tolist(), "tpr": tpr.tolist()}
            pr_data = {"precision": precision_curve.tolist(), "recall": recall_curve.tolist()}
        except Exception as e:
            print(f"[WARN] Could not compute ROC/PR data: {e}")

    # ===========================================================
    # SAVE MODELS
    # ===========================================================
    os.makedirs("models", exist_ok=True)
    joblib.dump(scaler, "models/scaler.joblib")
    joblib.dump(rf, "models/supervised_rf.joblib")
    joblib.dump(iso, "models/unsupervised_iso.joblib")
    if explainer:
        joblib.dump(explainer, "models/shap_explainer.joblib")

    # ===========================================================
    # FEATURE IMPORTANCE EXTRACTION
    # ===========================================================
    top_features = []
    try:
        importances = rf.feature_importances_
        feat_imp = sorted(
            zip(FEATURE_KEYS, importances),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        top_features = [{"feature": f, "importance": float(imp)} for f, imp in feat_imp]

        print("\n[INFO] Top 10 Important Features:")
        for f, imp in feat_imp:
            print(f"  {f:30s}: {imp:.5f}")
    except Exception as e:
        print(f"[WARN] Could not extract feature importances: {e}")

    # ===========================================================
    # METRICS JSON OUTPUT
    # ===========================================================
    metrics = {
        "accuracy": float(acc),
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "confusion_matrix": cm_arr,
        "roc_data": roc_data,
        "pr_data": pr_data,
        "top_features": top_features
    }

    out_dir = os.path.join("static", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "metrics.json")

    try:
        with open(out_path, "w") as fh:
            json.dump({"basic_metrics": metrics, **metrics}, fh, indent=2)
        print(f"[INFO] Metrics written to {out_path}")
    except Exception as e:
        print(f"[ERROR] Could not write metrics JSON: {e}")

    print("\n[INFO] Models saved in ./models/")

# ===============================================================
# ENTRY POINT
# ===============================================================
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train IDS models and save metrics.')
    parser.add_argument('--csv', required=True, help='Path to the training dataset (CSV)')
    args = parser.parse_args()
    main(args.csv)
