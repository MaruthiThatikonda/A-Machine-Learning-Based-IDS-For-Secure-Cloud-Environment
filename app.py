# app.py
import os
import json
import time
import sqlite3
import socket
import smtplib
import subprocess
import threading
import pandas as pd
import numpy as np
import traceback
import geoip2.database
from email.mime.text import MIMEText
from flask import (
    Flask, render_template, request, redirect,
    url_for, jsonify, session, g, make_response
)
from flask_socketio import SocketIO
from werkzeug.security import generate_password_hash, check_password_hash
from threading import Lock
from functools import wraps

# Local Imports
from inference import predict_flow, set_detector_params
from utils import init_db, log_prediction, DB_PATH, get_metrics_data, get_all_logs_csv

# ===============================================================
# Configuration & Globals
# ===============================================================
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'iot-sec-key-123')

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
init_db()

# Global IoT Device Config
IOT_CONFIG = {
    'device_name': 'Test Device',
    'ip_address': '127.0.0.1',
    'ipv4_enabled': True,
    'tcp_enabled': True,
    'syn_flood_rule': False,
    'admin_email': '',
    'status': 'OFF'  # ON/OFF
}

# ===============================================================
# EMAIL CONFIGURATION (CRITICAL SECTION)
# ===============================================================
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

# ✅ UPDATED: Your email is set below.
SMTP_USER = 'way2track01@gmail.com' 

# ⚠️ TODO: Replace the text below with your 16-char Google App Password
SMTP_PASS = 'masvczanrdbufpuq'

# Rate limit emails to avoid spamming (1 email per minute)
last_email_time = 0

# GeoIP Setup
GEOIP_DB = 'GeoLite2-City.mmdb'
try:
    geoip_reader = geoip2.database.Reader(GEOIP_DB)
    print(f"[INFO] ✅ GeoIP DB loaded: {GEOIP_DB}")
except FileNotFoundError:
    print("[WARN] ⚠️ GeoLite2-City.mmdb not found. Random coords will be used.")
    geoip_reader = None

# Threading for Replay
thread = None
thread_lock = Lock()

# ===============================================================
# Helpers
# ===============================================================
def get_local_ip():
    """Fetch local IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# Initialize IP in config
IOT_CONFIG['ip_address'] = get_local_ip()

def start_generator():
    import subprocess
    subprocess.Popen([
        "python", "generator.py",
        "--csv", "data/CICIDS2017_subset.csv",
        "--speed", "1"
    ])

threading.Thread(target=start_generator, daemon=True).start()

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped

def send_alert_email(attack_type, details):
    """Send SMTP notification to admin."""
    global last_email_time
    
    # Check if admin email is set in dashboard
    if not IOT_CONFIG['admin_email']:
        return
    
    # Rate limit: Only send 1 email every 60 seconds
    if time.time() - last_email_time < 60:
        return

    try:
        # Prepare the email content
        msg = MIMEText(f"ALERT: {attack_type} Detected!\n\nDetails:\n{json.dumps(details, indent=2)}")
        msg['Subject'] = f"[IDS] Security Alert: {attack_type}"
        msg['From'] = SMTP_USER
        msg['To'] = IOT_CONFIG['admin_email']

        # ✅ ENABLED: This block now sends the email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        
        print(f"[EMAIL] 📧 Sent alert to {IOT_CONFIG['admin_email']}")
        last_email_time = time.time()

    except Exception as e:
        print(f"[EMAIL ERROR] ❌ Failed to send email: {e}")
        print("Make sure you have generated a Google App Password and put it in app.py")

# ===============================================================
# Routes
# ===============================================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if request.method == 'POST':
        # Update Config
        IOT_CONFIG['device_name'] = request.form.get('device_name')
        IOT_CONFIG['ipv4_enabled'] = 'ipv4' in request.form
        IOT_CONFIG['tcp_enabled'] = 'tcp' in request.form
        IOT_CONFIG['syn_flood_rule'] = 'syn_flood' in request.form
        IOT_CONFIG['admin_email'] = request.form.get('admin_email')
        IOT_CONFIG['status'] = 'ON' if 'device_status' in request.form else 'OFF'
        print(f"[ADMIN] Config Updated: {IOT_CONFIG}")
        return redirect(url_for('admin'))
    
    # Refresh IP on load
    IOT_CONFIG['ip_address'] = get_local_ip()
    return render_template('admin.html', config=IOT_CONFIG, user=session.get('user'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if user and check_password_hash(user[2], password):
            session['user'] = user[1]
            return redirect(url_for('prediction'))
        return "Invalid credentials"
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed = generate_password_hash(password, method='pbkdf2:sha256')
        try:
            conn = get_db()
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Username exists"
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/prediction')
@login_required
def prediction():
    return render_template('prediction.html', user=session.get('user'), status=IOT_CONFIG['status'])

@app.route('/analysis')
@login_required
def analysis():
    return render_template('analysis.html', user=session.get('user'))

@app.route('/download_logs')
@login_required
def download_logs():
    csv_data = get_all_logs_csv()
    response = make_response(csv_data)
    response.headers["Content-Disposition"] = "attachment; filename=iot_attack_logs.csv"
    response.headers["Content-Type"] = "text/csv"
    return response

@app.route('/api/metrics_data')
@login_required
def metrics_data():
    data = get_metrics_data()
    return jsonify(data)

# ===============================================================
# Socket Logic & Replay
# ===============================================================
@socketio.on('new_flow')
def handle_new_flow(data):
    """Process flow: Rule Check -> Model Check -> Alert."""
    if IOT_CONFIG['status'] != 'ON':
        return  # Ignore traffic if Device is OFF

    try:
        ts = time.time()
        src_ip = data.get('src_ip', '0.0.0.0')
        dst_ip = data.get('dst_ip', '0.0.0.0')
        true_label = 0 if data.get('True_Label', 'BENIGN') == 'BENIGN' else 1
        
        # 1. Custom Rule Checks
        rule_violation = False
        reason = ""

        # Rule: TCP Disabled Policy
        proto = data.get('Protocol', 0) # Assuming 6 is TCP
        # Map protocol if string
        if isinstance(proto, str):
            proto_map = {'tcp': 6, 'udp': 17, 'icmp': 1}
            proto = proto_map.get(proto.lower(), 0)
        
        if not IOT_CONFIG['tcp_enabled'] and int(proto) == 6:
            rule_violation = True
            reason = "Policy Violation: TCP Disabled"

        # Rule: SYN Flood (High SYN count check)
        syn_count = float(data.get('SYN Flag Count', 0))
        if IOT_CONFIG['syn_flood_rule'] and syn_count > 0: # strict check for demo
            if syn_count >= 1: # In CSV, flags are often 0 or 1. High rate usually detected by volume, but we check flag presence here.
                rule_violation = True
                reason = "DDoS Signature: SYN Flood"

        # 2. ML Model Inference
        res = predict_flow(data)
        
        final_label = res['label']
        attack_score = res['attack_score']
        
        # Priority: Rule > Model
        if rule_violation:
            final_label = 1
            attack_score = 1.0
        elif final_label == 1:
            reason = "ML Anomaly Detection"

        # 3. Prepare Output
        out = {
            'ts': ts,
            'src_ip': src_ip,
            'dst_ip': dst_ip,
            'attack_score': attack_score,
            'label': final_label,
            'reason': reason,
            'shap_explain': res.get('shap_explain')
        }

        # GeoIP
        if geoip_reader:
            try:
                response = geoip_reader.city(src_ip)
                out['geo'] = {'lat': response.location.latitude, 'lon': response.location.longitude}
            except:
                out['geo'] = {'lat': np.random.uniform(-60, 70), 'lon': np.random.uniform(-180, 180)}
        else:
            out['geo'] = {'lat': np.random.uniform(-60, 70), 'lon': np.random.uniform(-180, 180)}

        # 4. Log & Alert
        log_prediction({
            'ts': ts,
            'src_ip': src_ip,
            'dst_ip': dst_ip,
            'features': json.dumps(data),
            'supervised_prob': res.get('supervised_prob'),
            'unsupervised_score': res.get('unsupervised_score'),
            'attack_score': attack_score,
            'label': final_label,
            'true_label': true_label,
            'latency_ms': res.get('latency_ms'),
            'reason': reason
        })

        socketio.emit('flow_result', out)
        
        if final_label == 1:
            socketio.emit('alarm', out)
            send_alert_email("DDoS / Intrusion", out)

    except Exception as e:
        print(f"[ERROR] {e}")
        traceback.print_exc()

if __name__ == '__main__':
    print("🚀 Cloud Security System Running on http://localhost:5000")
    subprocess.Popen([
    "python", "generator.py",
    "--csv", "data/CICIDS2017_subset.csv",
    "--speed", "1"
    ])
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)