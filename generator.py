import os
import pandas as pd
import time
import socketio
import argparse
import numpy as np

# Socket client
sio = socketio.Client()

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_full_path(csv_path):
    """Resolve correct CSV path (root/data/absolute)"""
    if os.path.isabs(csv_path):
        return csv_path

    # Try root
    path1 = os.path.join(BASE_DIR, csv_path)

    # Try data folder
    path2 = os.path.join(BASE_DIR, "data", csv_path)

    if os.path.exists(path1):
        return path1
    elif os.path.exists(path2):
        return path2
    else:
        return None


def replay(csv_path, server="http://localhost:5000", speed=1.0, flood=False):
    print(f"[INFO] Loading {csv_path}...")

    # Resolve path
    csv_full_path = get_full_path(csv_path)

    if not csv_full_path:
        print(f"[ERROR] File not found: {csv_path}")
        print("👉 Make sure file exists in root OR data/ folder")
        return

    print(f"[INFO] Using file: {csv_full_path}")

    # Load dataset
    df = pd.read_csv(csv_full_path)
    df.columns = df.columns.str.strip()

    # Flood mode
    if flood:
        print("[INFO] 🔥 FLOOD MODE ENABLED")
        df = df[df['Label'] == 'DDoS']
        if df.empty:
            print("[ERROR] No DDoS records found!")
            return
        speed *= 2

    records = df.to_dict(orient='records')
    print(f"[INFO] Loaded {len(records)} flows")

    # Connect to server
    print(f"[INFO] Connecting to {server}...")
    try:
        sio.connect(server)
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        print("👉 Make sure server is running OR URL is correct")
        return

    try:
        for i, row in enumerate(records):
            payload = row.copy()
            payload['True_Label'] = row.get('Label', 'BENIGN')

            # Simulate IPs
            if flood:
                payload['src_ip'] = f"192.168.1.{np.random.randint(100, 200)}"
                payload['dst_ip'] = "192.168.1.10"
            else:
                payload['src_ip'] = f"{np.random.randint(1,255)}.{np.random.randint(0,255)}.{np.random.randint(0,255)}.{np.random.randint(0,255)}"
                payload['dst_ip'] = f"{np.random.randint(1,255)}.{np.random.randint(0,255)}.{np.random.randint(0,255)}.{np.random.randint(0,255)}"

            sio.emit('new_flow', payload)

            if i % 100 == 0:
                print(f"[INFO] Sent {i} flows...")

            time.sleep(1.0 / speed)

    except KeyboardInterrupt:
        print("[INFO] Stopped manually")

    finally:
        sio.disconnect()
        print("[INFO] Disconnected")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--csv', default='CICIDS2017_subset.csv')
    parser.add_argument('--speed', type=float, default=1.0)
    parser.add_argument('--flood', action='store_true')
    parser.add_argument('--server', default="http://localhost:5000")

    args = parser.parse_args()

    replay(
        csv_path=args.csv,
        server=args.server,
        speed=args.speed,
        flood=args.flood
    )