import os
import json
import time
import sqlite3
import socket
import smtplib
import traceback
import geoip2.database

from email.mime.text import MIMEText
from flask import (
    Flask, render_template, request, redirect,
    url_for, jsonify, session, g, make_response
)
from flask_socketio import SocketIO
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Local imports
from inference import predict_flow
from utils import init_db, log_prediction, get_metrics_data, get_all_logs_csv

# ===============================================================
# PATH SETUP (CRITICAL)
# ===============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")
SQL_PATH = os.path.join(BASE_DIR, "nids.sql")
GEOIP_DB = os.path.join(BASE_DIR, "GeoLite2-City.mmdb")

# ===============================================================
# LOAD DB FROM SQL (FOR RENDER)
# ===============================================================
def load_db_from_sql():
    if not os.path.exists(DB_PATH):
        print("[INFO] Creating DB from SQL dump...")
        conn = sqlite3.connect(DB_PATH)
        if os.path.exists(SQL_PATH):
            with open(SQL_PATH, "r") as f:
                conn.executescript(f.read())
        conn.close()

load_db_from_sql()

# ===============================================================
# APP CONFIG
# ===============================================================
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'iot-sec-key-123')

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize DB tables if needed
init_db()

# ===============================================================
# GLOBAL CONFIG
# ===============================================================
IOT_CONFIG = {
    'device_name': 'Test Device',
    'ip_address': '127.0.0.1',
    'ipv4_enabled': True,
    'tcp_enabled': True,
    'syn_flood_rule': False,
    'admin_email': '',
    'status': 'OFF'
}

# ===============================================================
# EMAIL CONFIG
# ===============================================================
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USER = 'way2track01@gmail.com'
SMTP_PASS = 'masvczanrdbufpuq'

last_email_time = 0

# ===============================================================
# GEOIP SETUP
# ===============================================================
try:
    geoip_reader = geoip2.database.Reader(GEOIP_DB)
    print("[INFO] GeoIP loaded")
except:
    print("[WARN] GeoIP not found")
    geoip_reader = None

# ===============================================================
# HELPERS
# ===============================================================
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

IOT_CONFIG['ip_address'] = get_local_ip()

def get_db():
    if not hasattr(g, '_database'):
        g._database = sqlite3.connect(DB_PATH)
        g._database.row_factory = sqlite3.Row
    return g._database

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db:
        db.close()

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped

# ===============================================================
# EMAIL ALERT
# ===============================================================
def send_alert_email(attack_type, details):
    global last_email_time

    if not IOT_CONFIG['admin_email']:
        return

    if time.time() - last_email_time < 60:
        return

    try:
        msg = MIMEText(f"ALERT: {attack_type}\n\n{json.dumps(details, indent=2)}")
        msg['Subject'] = f"[IDS ALERT] {attack_type}"
        msg['From'] = SMTP_USER
        msg['To'] = IOT_CONFIG['admin_email']

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        last_email_time = time.time()

    except Exception as e:
        print("[EMAIL ERROR]", e)

# ===============================================================
# ROUTES
# ===============================================================
@app.route('/')
def index():
    return render_template('index.html')

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        user = conn.execute(
            'SELECT * FROM users WHERE username=?',
            (username,)
        ).fetchone()

        if user and check_password_hash(user['password'], password):
            session['user'] = user['username']
            return redirect(url_for('prediction'))

        return "Invalid credentials"

    return render_template('login.html')

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        try:
            conn = get_db()
            conn.execute(
                'INSERT INTO users (username, password) VALUES (?, ?)',
                (username, password)
            )
            conn.commit()
            return redirect(url_for('login'))

        except sqlite3.IntegrityError:
            return "Username exists"

    return render_template('register.html')

# ---------------- ADMIN PANEL ----------------
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    global IOT_CONFIG

    if request.method == 'POST':
        IOT_CONFIG['device_name'] = request.form.get('device_name')
        IOT_CONFIG['ipv4_enabled'] = 'ipv4' in request.form
        IOT_CONFIG['tcp_enabled'] = 'tcp' in request.form
        IOT_CONFIG['syn_flood_rule'] = 'syn_flood' in request.form
        IOT_CONFIG['admin_email'] = request.form.get('admin_email')
        IOT_CONFIG['status'] = 'ON' if 'device_status' in request.form else 'OFF'

        print("[ADMIN] Updated:", IOT_CONFIG)
        return redirect(url_for('admin'))

    IOT_CONFIG['ip_address'] = get_local_ip()

    return render_template('admin.html', config=IOT_CONFIG, user=session.get('user'))

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

# ---------------- PREDICTION PAGE ----------------
@app.route('/prediction')
@login_required
def prediction():
    return render_template('prediction.html', user=session['user'], status=IOT_CONFIG['status'])

# ---------------- ANALYSIS ----------------
@app.route('/analysis')
@login_required
def analysis():
    return render_template('analysis.html', user=session['user'])

# ---------------- DOWNLOAD LOGS ----------------
@app.route('/download_logs')
@login_required
def download_logs():
    csv_data = get_all_logs_csv()
    response = make_response(csv_data)
    response.headers["Content-Disposition"] = "attachment; filename=iot_attack_logs.csv"
    response.headers["Content-Type"] = "text/csv"
    return response

# ---------------- METRICS API ----------------
@app.route('/api/metrics_data')
@login_required
def metrics_data():
    return jsonify(get_metrics_data())

# ===============================================================
# SOCKET HANDLER
# ===============================================================
@socketio.on('new_flow')
def handle_new_flow(data):
    try:
        if IOT_CONFIG['status'] != 'ON':
            return

        res = predict_flow(data)

        socketio.emit('flow_result', res)

        if res['label'] == 1:
            socketio.emit('alarm', res)
            send_alert_email("Attack Detected", res)

        log_prediction({
            'ts': time.time(),
            'src_ip': data.get('src_ip'),
            'dst_ip': data.get('dst_ip'),
            'features': json.dumps(data),
            'attack_score': res.get('attack_score'),
            'label': res.get('label')
        })

    except Exception as e:
        print("[ERROR]", e)
        traceback.print_exc()

# ===============================================================
# MAIN
# ===============================================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Running on port {port}")
    socketio.run(app, host='0.0.0.0', port=port)