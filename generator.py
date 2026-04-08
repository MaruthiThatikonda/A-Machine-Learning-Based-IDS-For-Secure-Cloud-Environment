import os
import pandas as pd
import time
import socketio
import argparse
import numpy as np

sio = socketio.Client()

if not os.path.exists("data/CICIDS2017_subset.csv"):
    print("CSV file not found")
    exit()

def replay(csv_path, server='http://localhost:5000', speed=1.0, flood=False):
    print(f"[INFO] Loading {csv_path}...")
    df = pd.read_csv(csv_path)
    # Clean columns
    df.columns = df.columns.str.strip()
    
    if flood:
        print("[INFO] 🔥 FLOOD MODE ENABLED: Filtering for DDoS attacks only!")
        # Filter for DDoS label
        df = df[df['Label'] == 'DDoS']
        if df.empty:
            print("[ERROR] No DDoS records found in CSV to flood with!")
            return
        speed = speed * 2  # Double speed for flood simulation
    
    records = df.to_dict(orient='records')
    print(f"[INFO] Loaded {len(records)} flows. Connecting to {server}...")

    sio.connect(server)
    
    try:
        for i, row in enumerate(records):
            # Select features expected by model
            # Note: 'Label' is sent as 'True_Label' for validation
            payload = row.copy()
            payload['True_Label'] = row.get('Label', 'BENIGN')
            
            # Simulate specific IPs for DDoS
            if flood:
                payload['src_ip'] = f"192.168.1.{np.random.randint(100, 200)}" # Fake Botnet IPs
                payload['dst_ip'] = "192.168.1.10" # IoT Device IP (Target)
            else:
                payload['src_ip'] = f"{np.random.randint(1,255)}.{np.random.randint(0,255)}.{np.random.randint(0,255)}.{np.random.randint(0,255)}"
                payload['dst_ip'] = f"{np.random.randint(1,255)}.{np.random.randint(0,255)}.{np.random.randint(0,255)}.{np.random.randint(0,255)}"

            sio.emit('new_flow', payload)
            
            if i % 100 == 0:
                print(f"Sent {i} flows...")
            
            time.sleep(1.0 / speed)

    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        sio.disconnect()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', default='CICIDS2017_subset.csv')
    parser.add_argument('--speed', type=float, default=10.0)
    parser.add_argument('--flood', action='store_true', help="Generate DDoS Flood traffic")
    args = parser.parse_args()
    
    replay(args.csv, speed=args.speed, flood=args.flood)