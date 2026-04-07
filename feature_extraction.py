import numpy as np

# -------------------------------------------------------------------
# FEATURE EXTRACTION MODULE
# -------------------------------------------------------------------
# Converts a raw flow dictionary (from dataset or live packet data)
# into a numerical feature vector ready for the trained ML model.
# -------------------------------------------------------------------

# Define the features you used during training (must match train.py)
FEATURE_KEYS = [
    'Flow Duration',
    'Total Fwd Packets',
    'Total Backward Packets',
    'Total Length of Fwd Packets',
    'Total Length of Bwd Packets',
    'Fwd Packet Length Mean',
    'Bwd Packet Length Mean',
    'Flow IAT Mean',
    'Fwd IAT Mean',
    'Bwd IAT Mean',
    'Fwd PSH Flags',
    'Bwd PSH Flags',
    'Fwd URG Flags',
    'Bwd URG Flags',
    'Protocol'  # this will be encoded
]

# Encode protocol names into numeric IDs
PROTO_MAP = {'tcp': 0, 'udp': 1, 'icmp': 2}


def row_to_vector(row: dict):
    """
    Convert a flow dictionary to a numpy vector for model prediction.
    Handles missing values gracefully and encodes 'Protocol' numerically.

    Args:
        row (dict): Flow data (keys as defined in FEATURE_KEYS)
    Returns:
        np.ndarray: Feature vector of shape (1, n_features)
    """
    vec = []
    for key in FEATURE_KEYS:
        if key == 'Protocol':
            proto_val = str(row.get('Protocol', 'tcp')).lower()
            vec.append(float(PROTO_MAP.get(proto_val, 3)))  # default 3 if unknown
        else:
            try:
                vec.append(float(row.get(key, 0.0)))
            except Exception:
                vec.append(0.0)
    return np.array(vec).reshape(1, -1)
