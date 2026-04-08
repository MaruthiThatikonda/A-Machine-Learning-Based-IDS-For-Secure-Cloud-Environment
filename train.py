import os
import argparse
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
import shap  # <-- ADDED

# ===============================================================
# CONFIG
# ===============================================================

# Protocol numeric encoding map (same as in feature_extraction.py)
PROTO_MAP = {'tcp': 0, 'udp': 1, 'icmp': 2, 'others': 3}

# Define consistent feature keys (15 total)
FEATURE_KEYS = [
    'Protocol', 'Flow Duration', 'Total Fwd Packets', 'Total Backward Packets',
    'Total Length of Fwd Packets', 'Total Length of Bwd Packets',
    'Fwd Packet Length Mean', 'Bwd Packet Length Mean',
    'Flow IAT Mean', 'Fwd IAT Mean', 'Bwd IAT Mean',
    'Fwd PSH Flags', 'Bwd PSH Flags', 'Fwd URG Flags', 'Bwd URG Flags'
]

LABEL_COL = 'Label'

# ===============================================================
# UTILS
# ===============================================================

def encode_protocol(proto_value):
    """Convert protocol string to numeric."""
    if pd.isna(proto_value):
        return 3.0
    val = str(proto_value).lower()
    return float(PROTO_MAP.get(val, 3))


def preprocess_dataframe(df):
    """Prepare dataframe: encode protocol, fill missing, select features."""
    print(f"[INFO] Original columns: {len(df.columns)}")
    
    # Clean column names (remove leading/trailing spaces)
    df.columns = df.columns.str.strip()
    
    # 1. Handle missing/infinite values
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    # 2. Select FEATURE_KEYS and LABEL_COL, fill NaNs
    missing_cols = [col for col in FEATURE_KEYS if col not in df.columns]
    if missing_cols:
        print(f"[WARN] Missing required feature columns: {missing_cols}")
        print("[INFO] Please check your CSV.")
        for col in missing_cols:
            df[col] = 0.0 # Add missing columns as zero
            
    if LABEL_COL not in df.columns:
        raise ValueError(f"Label column '{LABEL_COL}' not found in CSV.")

    # Fill NaNs in feature columns
    df[FEATURE_KEYS] = df[FEATURE_KEYS].fillna(0.0)

    # 3. Encode 'Protocol'
    if 'Protocol' in df.columns:
        print("[INFO] Encoding 'Protocol' column...")
        # Assuming 'Protocol' might be object type, check for strings
        if df['Protocol'].dtype == 'object' or pd.api.types.is_string_dtype(df['Protocol']):
            df['Protocol'] = df['Protocol'].apply(encode_protocol)
        else:
            # If it's already numeric (e.g., 6, 17), map them
            df['Protocol'] = df['Protocol'].map({6: 0, 17: 1, 1: 2}).fillna(3)
    
    # 4. Encode 'Label'
    print("[INFO] Encoding 'Label' column...")
    y = df[LABEL_COL].apply(lambda x: 0 if str(x).strip() == 'BENIGN' else 1)
    
    # 5. Select final features
    X = df[FEATURE_KEYS].astype(np.float64)
    
    print(f"[INFO] Preprocessing complete. X shape: {X.shape}, y labels: {len(y)}")
    
    return X, y

# ===============================================================
# MAIN SCRIPT
# ===============================================================

def main(csv_path):
    print(f"[INFO] Loading CSV: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"[ERROR] Could not read CSV: {e}")
        return

    # Preprocess
    X, y = preprocess_dataframe(df)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
    print(f"[INFO] Data split: Train={len(y_train)}, Test={len(y_test)}")

    # Scale data
    print("[INFO] Scaling features...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    print(f"[INFO] Training RandomForestClassifier...")
    rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X_train_scaled, y_train)

    print(f"[INFO] Training IsolationForest (unsupervised)...")
    iso = IsolationForest(n_estimators=100, contamination=0.1, random_state=42, n_jobs=-1)
    iso.fit(X_train_scaled)

    # --- ADDED SHAP EXPLAINER ---
    print(f"[INFO] Creating SHAP explainer...")
    try:
        explainer = shap.TreeExplainer(rf)
        print("[INFO] SHAP explainer created successfully.")
    except Exception as e:
        print(f"[WARN] Could not create SHAP TreeExplainer: {e}")
        explainer = None
    # --- END ADDED SECTION ---

    # Evaluate RF
    y_pred = rf.predict(X_test_scaled)
    acc = accuracy_score(y_test, y_pred)
    print(f"\n[RESULT] Accuracy: {acc * 100:.2f}%")
    print(classification_report(y_test, y_pred))

    # Save models
    os.makedirs("models", exist_ok=True)
    joblib.dump(scaler, "models/scaler.joblib")
    joblib.dump(rf, "models/supervised_rf.joblib")
    joblib.dump(iso, "models/unsupervised_iso.joblib")
    
    # --- ADDED SHAP SAVE ---
    if explainer:
        joblib.dump(explainer, "models/shap_explainer.joblib")
        print("[INFO] SHAP explainer saved.")
    # --- END ADDED SECTION ---

    print(f"\n[INFO] Models saved in ./models/")
    print(f"[INFO] Scaler expects {scaler.n_features_in_} features.")
    print(f"[INFO] Training complete with {len(FEATURE_KEYS)} features.")
    print(f"[INFO] Feature list:\n  {FEATURE_KEYS}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='NIDS Model Trainer')
    parser.add_argument('--csv', required=True, help='Path to the CICIDS2017 subset CSV file')
    args = parser.parse_args()
    main(args.csv)