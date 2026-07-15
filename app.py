# /cybermind_aviator/app.py

import random
import time
import json
import os
os.environ["OPENCV_VIDEOIO_LOGGING_LEVEL"] = "0"
import sqlite3
import threading
import math
from flask import Flask, render_template, jsonify, request, Response
import requests
import io
import csv
import cv2
import numpy as np

app = Flask(__name__)

# --- Nominatim API for Geocoding ---
NOMINATIM_API = "https://nominatim.openstreetmap.org"
DB_PATH = "drone_intelligence.db"

# --- Live Software Drone Telemetry & State ---
drone_state = {
    "lat": 37.7749,
    "lon": -122.4194,
    "alt": 150.0,
    "speed": 0.0,
    "heading": 180.0,
    "battery": 100.0,
    "connection": 98,
    "override_active": False,
    "current_mission": "IDLE", # IDLE, PATROLLING, EVADING, RETURNING
    "last_update": time.strftime("%H:%M:%S")
}
# --- 5 Redundant Agents State ---
agents_lock = threading.Lock()
agents_state = [
    {"name": "Flight Agent Alpha", "type": "Redundant Flight Core", "status": "ACTIVE", "accuracy": "99.85%", "response_time": "1.25ms"},
    {"name": "Flight Agent Beta", "type": "Redundant Flight Core", "status": "STANDBY", "accuracy": "100.00%", "response_time": "0.00ms"},
    {"name": "Flight Agent Gamma", "type": "Redundant Flight Core", "status": "STANDBY", "accuracy": "100.00%", "response_time": "0.00ms"},
    {"name": "Flight Agent Delta", "type": "Redundant Flight Core", "status": "STANDBY", "accuracy": "100.00%", "response_time": "0.00ms"},
    {"name": "Flight Agent Epsilon", "type": "Redundant Flight Core", "status": "STANDBY", "accuracy": "100.00%", "response_time": "0.00ms"}
]
db_write_lock = threading.Lock()
_init_frame = np.zeros((480, 640, 3), dtype=np.uint8)
cv2.putText(_init_frame, "Initializing camera stream...", (140, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 150), 2)
_, _init_jpeg = cv2.imencode('.jpg', _init_frame)
latest_frame = _init_jpeg.tobytes()
latest_frame_lock = threading.Lock()

# --- Deep Learning Neural Networks (Pure Python Matrix Math Engine) ---

def list_dot(v, M):
    # Dot product of vector v (list) and matrix M (list of lists)
    out = []
    for col in range(len(M[0])):
        s = sum(v[row] * M[row][col] for row in range(len(v)))
        out.append(s)
    return out

class AnomalyAutoencoder:
    def __init__(self):
        # 4 inputs, 2 hidden neurons, 4 outputs
        # Normalized inputs: [speed (0-30), altitude (0-500), battery (0-100), heading (0-360)]
        self.W1 = [
            [ 0.5, -0.2],
            [-0.1,  0.8],
            [ 0.3,  0.4],
            [ 0.6, -0.7]
        ]
        self.b1 = [0.1, -0.2]
        self.W2 = [
            [ 0.7, -0.3,  0.1,  0.5],
            [-0.4,  0.6,  0.8, -0.2]
        ]
        self.b2 = [-0.1, 0.2, 0.1, -0.3]
        
    def sigmoid(self, x):
        try:
            return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, x))))
        except Exception:
            return 0.0
            
    def forward(self, x):
        # Hidden layer
        z1 = list_dot(x, self.W1)
        h = [self.sigmoid(z1[i] + self.b1[i]) for i in range(2)]
        # Output layer (reconstruction)
        z2 = list_dot(h, self.W2)
        y = [self.sigmoid(z2[i] + self.b2[i]) for i in range(4)]
        return y
        
    def calculate_loss(self, speed, alt, battery, heading):
        # Normalize inputs to [0, 1] range
        x = [
            max(0.0, min(1.0, speed / 30.0)),
            max(0.0, min(1.0, alt / 500.0)),
            max(0.0, min(1.0, battery / 100.0)),
            max(0.0, min(1.0, heading / 360.0))
        ]
        y = self.forward(x)
        loss = sum((x[i] - y[i]) ** 2 for i in range(4)) / 4.0
        return loss

class Proximity1DCNN:
    def __init__(self):
        # 1D Convolution kernel of size 3 (detects local spatial proximity trends)
        self.kernel = [0.1, 0.8, 0.1]
        # Max pooling pool size = 2
        # After Conv (36 -> 34) and MaxPool (34 -> 17), we have 17 pooled features
        # Dense weights mapping 17 features to 3 classes (Safe=0, Warning=1, Critical=2)
        self.dense_w = []
        for i in range(17):
            self.dense_w.append([0.05, 0.25, 0.70])
        self.dense_b = [0.1, 0.0, -0.4]
        
    def forward(self, x):
        # 1. 1D Convolution
        conv_out = []
        for i in range(len(x) - 2):
            val = x[i]*self.kernel[0] + x[i+1]*self.kernel[1] + x[i+2]*self.kernel[2]
            conv_out.append(val)
            
        # 2. Max Pooling (Pool size = 2)
        pooled = []
        for i in range(0, len(conv_out) - 1, 2):
            pooled.append(max(conv_out[i], conv_out[i+1]))
            
        # Guarantee feature size is 17
        while len(pooled) < 17:
            pooled.append(0.0)
        pooled = pooled[:17]
        
        # 3. Dense Classification Layer
        logits = [0.0, 0.0, 0.0]
        for col in range(3):
            s = sum(pooled[row] * self.dense_w[row][col] for row in range(17)) + self.dense_b[col]
            logits[col] = s
            
        # 4. Softmax probability output
        try:
            exp_logits = [math.exp(max(-20.0, min(20.0, val))) for val in logits]
            sum_exp = sum(exp_logits)
            probs = [val / sum_exp for val in exp_logits]
        except Exception:
            probs = [0.33, 0.33, 0.34]
            
        max_prob_index = probs.index(max(probs))
        return max_prob_index, probs

class DRLAutopilotPolicy:
    def __init__(self):
        # Inputs: [normalized mission, speed, altitude, heading, battery] -> 5 inputs
        # Hidden Layer: 8 neurons
        # Action outputs: [yaw left, yaw right, speed up, speed down, climb, descend, hold] -> 7 classes
        self.W1 = [[random.uniform(-0.3, 0.3) for _ in range(8)] for _ in range(5)]
        self.b1 = [0.0] * 8
        self.W2 = [[random.uniform(-0.3, 0.3) for _ in range(7)] for _ in range(8)]
        self.b2 = [0.0] * 7
        
    def forward(self, state):
        # Layer 1
        z1 = list_dot(state, self.W1)
        h = [max(0.0, z1[i] + self.b1[i]) for i in range(8)] # ReLU
        # Layer 2
        z2 = list_dot(h, self.W2)
        logits = [z2[i] + self.b2[i] for i in range(7)]
        
# Instantiate Deep Learning models
telemetry_autoencoder = AnomalyAutoencoder()
proximity_cnn = Proximity1DCNN()
autopilot_policy = DRLAutopilotPolicy()

# --- Database Helper Functions ---

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB_PATH):
        conn = get_db_connection()
        with open('schema.sql', 'r') as f:
            conn.executescript(f.read())
        conn.commit()
        # Seed initial system logs
        cursor = conn.cursor()
        cursor.execute("INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)", 
                       ("Flight Plan Controller", "INFO", "System initialized. Database created successfully."))
        cursor.execute("INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)", 
                       ("Diagnostics Registrar", "INFO", "Telemetry logger startup sequence complete."))
        conn.commit()
        conn.close()

# --- Background Agent Loop Simulation ---

def run_agents_loop():
    init_db()
    while True:
        time.sleep(2.0)
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 1. Manage Active / Standby and Auto-Failover Logic
            active_agent = None
            with agents_lock:
                # Find current active agent
                for agent in agents_state:
                    if agent["status"] == "ACTIVE":
                        active_agent = agent
                        break
                
                # If no agent is ACTIVE, check if we can failover to a STANDBY agent
                if not active_agent:
                    for agent in agents_state:
                        if agent["status"] == "STANDBY":
                            agent["status"] = "ACTIVE"
                            agent["accuracy"] = f"{random.uniform(98.5, 99.9):.2f}%"
                            agent["response_time"] = f"{random.uniform(1.2, 8.5):.2f}ms"
                            active_agent = agent
                            
                            cursor.execute(
                                "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                                ("Flight Operations Core", "WARNING", "No active flight controller! Failover protocol initiated.")
                            )
                            cursor.execute(
                                "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                                (active_agent["name"], "INFO", "Agent automatically activated. Resuming all flight systems.")
                            )
                            break

            # 2. Simulate Random Subsystem Failure (4% chance per iteration)
            if active_agent and random.random() < 0.04:
                with agents_lock:
                    active_agent["status"] = "FAILED"
                    active_agent["accuracy"] = "0.00%"
                    active_agent["response_time"] = "0.00ms"
                    failed_name = active_agent["name"]
                    
                    cursor.execute(
                        "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                        (failed_name, "CRITICAL", "Critical hardware exception: Diagnostic heartbeat lost!")
                    )
                    
                    # Try to failover to next standby
                    next_agent = None
                    for agent in agents_state:
                        if agent["status"] == "STANDBY":
                            agent["status"] = "ACTIVE"
                            agent["accuracy"] = f"{random.uniform(98.5, 99.9):.2f}%"
                            agent["response_time"] = f"{random.uniform(1.2, 8.5):.2f}ms"
                            next_agent = agent
                            break
                    
                    if next_agent:
                        cursor.execute(
                            "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                            ("Flight Operations Core", "WARNING", f"Failover engaged: {next_agent['name']} promoted to ACTIVE.")
                        )
                        cursor.execute(
                            "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                            (next_agent["name"], "INFO", "Syncing sensors and navigation databases.")
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                            ("Flight Operations Core", "CRITICAL", "ALL AUTONOMOUS AGENTS FAILED! Auto-pilot is completely OFFLINE.")
                        )
                    
                    active_agent = next_agent

            # Update connection status slightly
            drone_state["connection"] = random.randint(92, 99)
            
            # --- Deep Learning 1: Autopilot Policy (DRL) ---
            # Inputs: mission_type, normalized speed, normalized altitude, normalized heading, normalized battery
            mission_mapping = {"IDLE": 0, "PATROLLING": 1, "EVADING": 2, "RETURNING": 3}
            m_val = mission_mapping.get(drone_state["current_mission"], 0)
            state_vector = [
                m_val / 3.0,
                drone_state["speed"] / 30.0,
                drone_state["alt"] / 500.0,
                drone_state["heading"] / 360.0,
                drone_state["battery"] / 100.0
            ]
            action = autopilot_policy.forward(state_vector)
            
            # Apply network action outputs to flight variables dynamically if not IDLE
            if drone_state["current_mission"] != "IDLE":
                if action == 0: # Yaw Left
                    drone_state["heading"] = (drone_state["heading"] - 5.0) % 360
                elif action == 1: # Yaw Right
                    drone_state["heading"] = (drone_state["heading"] + 5.0) % 360
                elif action == 2: # Speed Up
                    drone_state["speed"] = min(drone_state["speed"] + 0.5, 25.0)
                elif action == 3: # Speed Down
                    drone_state["speed"] = max(drone_state["speed"] - 0.5, 5.0)
                elif action == 4: # Climb
                    drone_state["alt"] = min(drone_state["alt"] + 1.5, 400.0)
                elif action == 5: # Descend
                    drone_state["alt"] = max(drone_state["alt"] - 1.5, 80.0)
            
            # --- Deep Learning 2: Proximity Conv1D CNN ---
            # Generate 36 distance samples representing LiDAR radar array
            base_dist = 2.0 if drone_state["current_mission"] == "EVADING" else 8.0
            lidar_distances = [random.uniform(base_dist - 1.0, base_dist + 5.0) for _ in range(36)]
            risk_class, risk_probs = proximity_cnn.forward(lidar_distances)
            
            # Update flight telemetry based on mission status
            if drone_state["current_mission"] == "PATROLLING":
                drone_state["speed"] = round(random.uniform(10.0, 15.0), 1)
                drone_state["alt"] = round(drone_state["alt"] + random.uniform(-0.5, 0.5), 1)
                drone_state["alt"] = max(100.0, min(drone_state["alt"], 350.0))
                drone_state["heading"] = (drone_state["heading"] + 5) % 360
                
                # Move coordinates in direction of heading
                rad = math.radians(drone_state["heading"])
                d_lat = (drone_state["speed"] * math.cos(rad)) / 111000.0
                d_lon = (drone_state["speed"] * math.sin(rad)) / (111000.0 * math.cos(math.radians(drone_state["lat"])))
                drone_state["lat"] += d_lat
                drone_state["lon"] += d_lon
                drone_state["battery"] = max(0.0, round(drone_state["battery"] - 0.05, 2))
                
            elif drone_state["current_mission"] == "EVADING":
                drone_state["speed"] = round(random.uniform(18.0, 24.0), 1)
                drone_state["alt"] = round(drone_state["alt"] + random.uniform(1.5, 3.0), 1)
                drone_state["alt"] = min(drone_state["alt"], 450.0)
                drone_state["heading"] = (drone_state["heading"] + 25) % 360
                
                # Evasive movement
                rad = math.radians(drone_state["heading"])
                d_lat = (drone_state["speed"] * math.cos(rad)) / 111000.0
                d_lon = (drone_state["speed"] * math.sin(rad)) / (111000.0 * math.cos(math.radians(drone_state["lat"])))
                drone_state["lat"] += d_lat
                drone_state["lon"] += d_lon
                drone_state["battery"] = max(0.0, round(drone_state["battery"] - 0.1, 2))
                
            elif drone_state["current_mission"] == "RETURNING":
                target_lat = 37.7749
                target_lon = -122.4194
                dy = target_lat - drone_state["lat"]
                dx = target_lon - drone_state["lon"]
                dist = math.sqrt(dx*dx + dy*dy)
                
                if dist < 0.0001:
                    drone_state["current_mission"] = "IDLE"
                    drone_state["speed"] = 0.0
                    drone_state["alt"] = 0.0
                else:
                    drone_state["speed"] = 12.0
                    drone_state["heading"] = math.degrees(math.atan2(dx, dy)) % 360
                    step = 0.0001
                    drone_state["lat"] += (dy / dist) * step
                    drone_state["lon"] += (dx / dist) * step
                    if drone_state["alt"] > 10.0:
                        drone_state["alt"] -= 1.0
                    drone_state["battery"] = max(0.0, round(drone_state["battery"] - 0.04, 2))
                    
            else: # IDLE
                drone_state["speed"] = 0.0
                if drone_state["alt"] < 1.0 and drone_state["battery"] < 100.0:
                    drone_state["battery"] = min(100.0, round(drone_state["battery"] + 0.5, 2))
                elif drone_state["battery"] < 100.0:
                    drone_state["battery"] = max(0.0, round(drone_state["battery"] - 0.01, 2))
            
            # 3. If there is an active agent, it performs the system tasks & writes logs under its name
            if active_agent:
                # Task A: Diagnostics Registrar (Autoencoder Telemetry Check)
                ae_loss = telemetry_autoencoder.calculate_loss(
                    drone_state["speed"],
                    drone_state["alt"],
                    drone_state["battery"],
                    drone_state["heading"]
                )
                
                cursor.execute(
                    "INSERT INTO telemetry_logs (speed, altitude, battery, heading) VALUES (?, ?, ?, ?)",
                    (drone_state["speed"], drone_state["alt"], drone_state["battery"], drone_state["heading"])
                )
                
                # Anomaly check
                is_anomaly = ae_loss > 0.15 or drone_state["battery"] < 30.0
                log_level = "WARNING" if is_anomaly else "INFO"
                status_text = "ANOMALY DETECTED" if is_anomaly else "HEALTHY"
                
                cursor.execute(
                    "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                    (active_agent["name"], log_level, f"Autoencoder loss={ae_loss:.5f} ({status_text}). Speed={drone_state['speed']}m/s, Alt={drone_state['alt']}m, Batt={drone_state['battery']}%")
                )
                
                # Task B: Position Pathing Agent (GPS Coordinates)
                cursor.execute(
                    "INSERT INTO gps_logs (lat, lon, alt, quality, source) VALUES (?, ?, ?, ?, ?)",
                    (drone_state["lat"], drone_state["lon"], drone_state["alt"], "Excellent" if drone_state["connection"] > 94 else "Good", "Path Coordinates Logger")
                )
                cursor.execute(
                    "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                    (active_agent["name"], "INFO", f"Coordinate registered: {drone_state['lat']:.6f}, {drone_state['lon']:.6f}")
                )
                
                # Task C: Proximity Safety Agent (Collision warning using Conv1D CNN)
                if drone_state["speed"] > 0:
                    if risk_class == 2: # CRITICAL Avoidance
                        distance = round(min(lidar_distances), 1)
                        angle = random.randint(-40, 40)
                        cursor.execute(
                            "INSERT INTO obstacle_logs (distance, angle, status, action) VALUES (?, ?, ?, ?)",
                            (distance, angle, "CRITICAL", "CNN AUTO AVOIDANCE ENGAGED")
                        )
                        cursor.execute(
                            "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                            (active_agent["name"], "CRITICAL", f"Conv1D CNN: Critical obstacle at {distance}m. Evasion vector engaged.")
                        )
                        drone_state["current_mission"] = "EVADING"
                        drone_state["heading"] = (drone_state["heading"] + 90) % 360
                    elif risk_class == 1 and random.random() < 0.2: # WARNING Alert
                        distance = round(min(lidar_distances), 1)
                        angle = random.randint(-40, 40)
                        cursor.execute(
                            "INSERT INTO obstacle_logs (distance, angle, status, action) VALUES (?, ?, ?, ?)",
                            (distance, angle, "WARNING", "CNN MONITORING")
                        )
                        cursor.execute(
                            "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                            (active_agent["name"], "WARNING", f"Conv1D CNN: Advisory obstacle at {distance}m. Adjusting path.")
                        )
                
                # Task D: Optical Activity Registrar Agent (Threat scanning)
                if random.random() < 0.08:
                    threats = [
                        ("Signal Anomaly", "Intermittent signal disruption detected in area"),
                        ("Secondary Aircraft", "Unregistered signature detected at 400m altitude"),
                        ("Network Activity", "External request scanned and blocked")
                    ]
                    t_type, t_details = random.choice(threats)
                    confidence = random.randint(70, 95)
                    cursor.execute(
                        "INSERT INTO threat_logs (type, confidence, details, status, lat, lon) VALUES (?, ?, ?, ?, ?, ?)",
                        (t_type, confidence, t_details, "MONITORING", drone_state["lat"], drone_state["lon"])
                    )
                    cursor.execute(
                        "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                        (active_agent["name"], "WARNING", f"Object activity registered: {t_type} (Confidence {confidence}%)")
                    )
                
                # Task E: Flight Plan Controller Agent (Autopilot check-in using Policy Network)
                if random.random() < 0.10:
                    cursor.execute(
                        "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                        (active_agent["name"], "INFO", f"Autopilot policy action value={action} (Autopilot State: {drone_state['current_mission']})")
                    )
            
            # Keep log table sizes healthy
            cursor.execute("DELETE FROM system_logs WHERE id NOT IN (SELECT id FROM system_logs ORDER BY id DESC LIMIT 150)")
            cursor.execute("DELETE FROM gps_logs WHERE id NOT IN (SELECT id FROM gps_logs ORDER BY id DESC LIMIT 150)")
            cursor.execute("DELETE FROM threat_logs WHERE id NOT IN (SELECT id FROM threat_logs ORDER BY id DESC LIMIT 150)")
            cursor.execute("DELETE FROM obstacle_logs WHERE id NOT IN (SELECT id FROM obstacle_logs ORDER BY id DESC LIMIT 150)")
            cursor.execute("DELETE FROM telemetry_logs WHERE id NOT IN (SELECT id FROM telemetry_logs ORDER BY id DESC LIMIT 150)")
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error in background agents loop: {e}")

def background_detection_loop():
    """Simulated optical detection loop - logs threat detections to the database.
    Camera display is handled by the browser via getUserMedia, so this thread
    does NOT open the physical webcam (avoids Windows single-access lock)."""

    while True:
        try:
            # Simulated target generation for the threat log
            if drone_state["current_mission"] in ("EVADING", "PATROLLING") or random.random() < 0.15:
                confidence = random.randint(78, 95)
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO threat_logs (type, confidence, details, status, lat, lon) VALUES (?, ?, ?, ?, ?, ?)",
                        ("Person Detected", confidence, "Optical sensor recorded human target path obstruction.", "MONITORING", drone_state["lat"], drone_state["lon"])
                    )
                    active_agent = next((a for a in agents_state if a["status"] == "ACTIVE"), None)
                    agent_name = active_agent["name"] if active_agent else "Flight Operations Core"
                    cursor.execute(
                        "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                        (agent_name, "WARNING", f"Backend Optical Registrar: Human target detected (Confidence {confidence}%)")
                    )
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
        except Exception:
            pass

        time.sleep(2.0)  # Check every 2 seconds

# Load Haar cascade once at module level for face detection API
_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
_face_cascade = cv2.CascadeClassifier(_cascade_path) if os.path.exists(_cascade_path) else None

@app.route("/api/surveillance/detect", methods=["POST"])
def api_surveillance_detect():
    """Receive a JPEG frame from the browser, run Haar cascade face detection,
    return real bounding box coordinates."""
    try:
        file = request.files.get("frame")
        if file is None:
            return jsonify({"detections": []})

        # Decode the uploaded JPEG into an OpenCV image
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"detections": []})

        detections = []
        if _face_cascade is not None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = _face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            h_img, w_img = img.shape[:2]
            for (x, y, w, h) in faces:
                detections.append({
                    "label": "PERSON",
                    "confidence": 92,
                    "x": round(x / w_img, 4),
                    "y": round(y / h_img, 4),
                    "w": round(w / w_img, 4),
                    "h": round(h / h_img, 4)
                })

        return jsonify({"detections": detections})
    except Exception as e:
        return jsonify({"detections": [], "error": str(e)})

# --- Existing Flask Routes ---

@app.route("/")
def home():
    return render_template("index.html", title="Command Dashboard")

@app.route("/gps-console")
def gps_console():
    return render_template("gps_console.html", title="GPS Coordinates")

@app.route("/surveillance")
def surveillance():
    return render_template("surveillance.html", title="Optical Capture")

@app.route("/manual-control")
def manual_control():
    return render_template("manual_control.html", title="Manual Override")

@app.route("/alerts")
def alerts():
    return render_template("alerts.html", title="Security Logs")

@app.route("/log-explorer")
def log_explorer():
    return render_template("log_explorer.html", title="Operations Database")

# --- API Endpoints ---

@app.route("/api/dashboard_data")
def api_dashboard_data():
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get latest logs for the operations registry (last 12 logs)
    cursor.execute("SELECT timestamp, agent_name, log_level, message FROM system_logs ORDER BY id DESC LIMIT 12")
    db_logs = cursor.fetchall()
    
    co_drive_logs = []
    for log in db_logs:
        timestamp_part = log["timestamp"]
        if " " in timestamp_part:
            timestamp_part = timestamp_part.split()[1]
        co_drive_logs.append({
            "time": timestamp_part,
            "type": log["log_level"],
            "source": log["agent_name"],
            "message": log["message"],
            "status": "ACTIVE" if log["log_level"] in ("WARNING", "CRITICAL") else "COMPLETED"
        })
        
    # Get recent anomalies from threat_logs
    cursor.execute("SELECT type, details, status, confidence FROM threat_logs ORDER BY id DESC LIMIT 5")
    db_threats = cursor.fetchall()
    cyber_threats = []
    for threat in db_threats:
        cyber_threats.append({
            "type": threat["type"],
            "details": threat["details"],
            "status": threat["status"],
            "confidence": int(threat["confidence"])
        })
        
    # Compile agent status for dashboard
    controllers = []
    with agents_lock:
        for agent in agents_state:
            cursor.execute("SELECT timestamp, message FROM system_logs WHERE agent_name = ? ORDER BY id DESC LIMIT 1", (agent["name"],))
            last_log = cursor.fetchone()
            
            if last_log:
                last_msg = last_log["message"]
                last_time = last_log["timestamp"]
                if " " in last_time:
                    last_time = last_time.split()[1]
            else:
                if agent["status"] == "STANDBY":
                    last_msg = "Passive standby mode."
                elif agent["status"] == "FAILED":
                    last_msg = "Critical error: Diagnostic heartbeat lost!"
                else:
                    last_msg = "Diagnostics initialized. Syncing..."
                last_time = time.strftime("%H:%M:%S")
                
            controllers.append({
                "name": agent["name"],
                "type": agent["type"],
                "status": agent["status"],
                "accuracy": agent["accuracy"],
                "response_time": agent["response_time"],
                "last_update": last_time,
                "message": last_msg
            })
            
    conn.close()
    
    # Calculate alerts count, including any FAILED redundant agents
    failed_agents_count = sum(1 for a in agents_state if a["status"] == "FAILED")
    alerts_count = len([c for c in cyber_threats if c["status"] == "ACTIVE"]) + (3 if drone_state["current_mission"] == "EVADING" else 0) + failed_agents_count
    
    system_status = {
        "connection": drone_state["connection"],
        "system_time": time.strftime("%H:%M:%S"),
        "gps_status": "STRONG" if drone_state["connection"] > 94 else "FAIR",
        "emergency_alerts": max(0, alerts_count)
    }
    
    return jsonify({
        "controllers": controllers,
        "co_drive_logs": co_drive_logs,
        "cyber_threats": cyber_threats,
        "system_status": system_status
    })

# API endpoint to handle manual agent actions (fail, pause, activate, recover)
@app.route("/api/agent/action", methods=["POST"])
def api_agent_action():
    data = request.get_json() or {}
    agent_name = data.get("agent_name")
    action = data.get("action") # fail, pause, activate, recover
    
    if not agent_name or not action:
        return jsonify({"error": "Missing agent_name or action"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    success = False
    message = ""
    
    with agents_lock:
        target_agent = None
        for agent in agents_state:
            if agent["name"] == agent_name:
                target_agent = agent
                break
                
        if target_agent:
            if action == "fail":
                if target_agent["status"] in ("ACTIVE", "STANDBY"):
                    target_agent["status"] = "FAILED"
                    target_agent["accuracy"] = "0.00%"
                    target_agent["response_time"] = "0.00ms"
                    
                    cursor.execute(
                        "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                        (target_agent["name"], "CRITICAL", "Manual simulation: Subsystem failure triggered.")
                    )
                    
                    # Trigger failover if the failed agent was active
                    next_agent = None
                    for agent in agents_state:
                        if agent["status"] == "STANDBY":
                            agent["status"] = "ACTIVE"
                            agent["accuracy"] = f"{random.uniform(98.5, 99.9):.2f}%"
                            agent["response_time"] = f"{random.uniform(1.2, 8.5):.2f}ms"
                            next_agent = agent
                            break
                            
                    if next_agent:
                        cursor.execute(
                            "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                            ("Flight Operations Core", "WARNING", f"Failover triggered: activating {next_agent['name']}.")
                        )
                        cursor.execute(
                            "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                            (next_agent["name"], "INFO", f"Activated as primary controller. Syncing telemetry.")
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                            ("Flight Operations Core", "CRITICAL", "ALL FLIGHT CORE AGENTS FAILED! Safe mode engaged.")
                        )
                    success = True
                    message = f"Simulated failure on {agent_name}."
                    
            elif action == "pause":
                if target_agent["status"] == "ACTIVE":
                    target_agent["status"] = "STANDBY"
                    target_agent["accuracy"] = "100.00%"
                    target_agent["response_time"] = "0.00ms"
                    
                    cursor.execute(
                        "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                        (target_agent["name"], "INFO", "Agent manually paused. Entering standby.")
                    )
                    
                    # Activate next standby
                    next_agent = None
                    for agent in agents_state:
                        if agent["status"] == "STANDBY" and agent["name"] != agent_name:
                            agent["status"] = "ACTIVE"
                            agent["accuracy"] = f"{random.uniform(98.5, 99.9):.2f}%"
                            agent["response_time"] = f"{random.uniform(1.2, 8.5):.2f}ms"
                            next_agent = agent
                            break
                            
                    if next_agent:
                        cursor.execute(
                            "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                            ("Flight Operations Core", "WARNING", f"Failover triggered: activating {next_agent['name']}.")
                        )
                        cursor.execute(
                            "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                            (next_agent["name"], "INFO", f"Activated as primary controller. Syncing telemetry.")
                        )
                    success = True
                    message = f"Paused agent {agent_name}."
                elif target_agent["status"] == "STANDBY":
                    success = True
                    message = f"Agent {agent_name} is already standby."
                    
            elif action == "activate":
                for agent in agents_state:
                    if agent["name"] == agent_name:
                        agent["status"] = "ACTIVE"
                        agent["accuracy"] = f"{random.uniform(98.5, 99.9):.2f}%"
                        agent["response_time"] = f"{random.uniform(1.2, 8.5):.2f}ms"
                    elif agent["status"] == "ACTIVE":
                        agent["status"] = "STANDBY"
                        agent["accuracy"] = "100.00%"
                        agent["response_time"] = "0.00ms"
                
                cursor.execute(
                    "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                    (target_agent["name"], "INFO", "Agent manually set to active primary controller.")
                )
                success = True
                message = f"Activated agent {agent_name}."
                
            elif action == "recover":
                if target_agent["status"] == "FAILED":
                    target_agent["status"] = "STANDBY"
                    target_agent["accuracy"] = "100.00%"
                    target_agent["response_time"] = "0.00ms"
                    
                    cursor.execute(
                        "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                        (target_agent["name"], "INFO", "Subsystem recovered and reset to standby.")
                    )
                    
                    # If no agent is currently active, activate it
                    has_active = any(a["status"] == "ACTIVE" for a in agents_state)
                    if not has_active:
                        target_agent["status"] = "ACTIVE"
                        target_agent["accuracy"] = f"{random.uniform(98.5, 99.9):.2f}%"
                        target_agent["response_time"] = f"{random.uniform(1.2, 8.5):.2f}ms"
                        cursor.execute(
                            "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                            (target_agent["name"], "INFO", "No active agent found. Promoted recovered agent to ACTIVE.")
                        )
                    success = True
                    message = f"Recovered agent {agent_name}."
                    
    conn.commit()
    conn.close()
    
    if success:
        return jsonify({"status": "success", "message": message, "agents": agents_state})
    else:
        return jsonify({"error": f"Failed to perform action {action} on agent {agent_name}"}), 400

# Helper function to run parallel backup and database purge
def run_backup_and_delete():
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        
    timestamp = int(time.time())
    tables = ["system_logs", "gps_logs", "threat_logs", "obstacle_logs", "telemetry_logs"]
    
    threads = []
    errors = []
    
    def worker(table_name):
        try:
            # 1. Fetch data from table (Read is safe concurrently)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            data = [dict(row) for row in rows]
            conn.close()
            
            if not data:
                return # Nothing to backup
                
            # 2. Write to backup file (Parallel File I/O)
            filepath = os.path.join(backup_dir, f"backup_{table_name}_{timestamp}.json")
            with open(filepath, "w") as f:
                json.dump(data, f, indent=4)
                
            # 3. Purge from database under a write lock to avoid conflicts
            with db_write_lock:
                conn_write = get_db_connection()
                cursor_write = conn_write.cursor()
                ids = [row["id"] for row in data]
                id_str = ",".join(str(i) for i in ids)
                cursor_write.execute(f"DELETE FROM {table_name} WHERE id IN ({id_str})")
                conn_write.commit()
                conn_write.close()
        except Exception as e:
            errors.append(f"{table_name}: {str(e)}")
            
    # Start thread per table for parallel execution
    for table in tables:
        t = threading.Thread(target=worker, args=(table,))
        threads.append(t)
        t.start()
        
    # Wait for all parallel jobs to complete
    for t in threads:
        t.join()
        
    # Log the successful backup event
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
        ("Flight Operations Core", "INFO", f"Parallel backup and purge complete. Saved {len(tables)} tables to '{backup_dir}/'.")
    )
    conn.commit()
    conn.close()
    
    return errors

# API override to purge all database logs
@app.route("/api/override/delete_logs", methods=["POST"])
def api_override_delete_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    tables = ["system_logs", "gps_logs", "threat_logs", "obstacle_logs", "telemetry_logs"]
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")
    cursor.execute(
        "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
        ("Flight Operations Core", "INFO", "Manual purge completed. All system logs deleted.")
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "All database logs deleted successfully."})

# API override to backup and purge database logs parallelly
@app.route("/api/override/backup_logs", methods=["POST"])
def api_override_backup_logs():
    errors = run_backup_and_delete()
    if errors:
        return jsonify({"status": "error", "errors": errors}), 500
    return jsonify({"status": "success", "message": "Parallel backup and delete completed successfully."})

# API override to shut down the server process (Emergency Kill Switch)
@app.route("/api/override/kill_server", methods=["POST"])
def api_override_kill_server():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
        ("System Failsafe", "CRITICAL", "Emergency Kill Switch activated! Shutting down all systems.")
    )
    conn.commit()
    conn.close()
    
    # Delay slightly to allow the HTTP response to be transmitted
    def shutdown():
        time.sleep(0.5)
        os._exit(0)
        
    threading.Thread(target=shutdown).start()
    return jsonify({"status": "success", "message": "Emergency shutdown initiated. Server offline."})

# API to receive frame from frontend, process it on backend, and return target detections
@app.route("/api/surveillance/analyze_frame", methods=["POST"])
def api_surveillance_analyze_frame():
    data = request.get_json() or {}
    image_data = data.get("image")
    if not image_data:
        return jsonify({"error": "No image data"}), 400
        
    predictions = []
    
    # Simulate high-fidelity target detection. If the drone is EVADING or PATROLLING,
    # or randomly (approx 5% of frames), detect a target "person" to make it realistic.
    # Also detect secondary objects like "landing pad" or "unregistered aircraft" depending on coordinates.
    should_detect_human = False
    
    if drone_state["current_mission"] == "EVADING" or random.random() < 0.05:
        should_detect_human = True
        
    if should_detect_human:
        # Generate a random bounding box in 640x480 space
        x = random.randint(120, 240)
        y = random.randint(100, 200)
        w = random.randint(150, 220)
        h = random.randint(200, 250)
        score = round(random.uniform(0.72, 0.96), 2)
        predictions.append({
            "class": "person",
            "score": score,
            "bbox": [x, y, w, h]
        })
        
    # Occasionally detect non-threat static targets
    if random.random() < 0.03:
        predictions.append({
            "class": "landing pad",
            "score": round(random.uniform(0.85, 0.98), 2),
            "bbox": [300, 250, 120, 100]
        })
        
    return jsonify({"status": "success", "predictions": predictions})

# Streaming endpoint for continuous background camera feed
@app.route("/api/surveillance/video_feed")
def api_surveillance_video_feed():
    def gen():
        while True:
            frame_bytes = None
            with latest_frame_lock:
                frame_bytes = latest_frame
                
            if frame_bytes is not None:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.06)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

# API route to fetch data for dashboard analytics visualizations
@app.route("/api/analytics_data")
def api_analytics_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch last 20 telemetry records (for Speed and Altitude trends)
    cursor.execute("SELECT speed, altitude, battery, heading FROM telemetry_logs ORDER BY id DESC LIMIT 20")
    telemetry_rows = cursor.fetchall()
    
    # 2. Fetch count of system logs by level (for Severity distribution)
    cursor.execute("SELECT log_level, COUNT(*) as cnt FROM system_logs GROUP BY log_level")
    log_counts = {"INFO": 0, "WARNING": 0, "CRITICAL": 0}
    for row in cursor.fetchall():
        lvl = row["log_level"]
        if lvl in log_counts:
            log_counts[lvl] = row["cnt"]
            
    conn.close()
    
    # Reverse rows to show chronological order
    telemetry_data = []
    for r in reversed(telemetry_rows):
        telemetry_data.append({
            "speed": r["speed"],
            "altitude": r["altitude"],
            "battery": r["battery"],
            "heading": r["heading"]
        })
        
    # Generate 12-point LiDAR distance map dynamically based on drone's active sonar calculations
    base_dist = 2.0 if drone_state["current_mission"] == "EVADING" else 7.5
    lidar_distances = [round(random.uniform(base_dist - 0.8, base_dist + 4.2), 1) for _ in range(12)]
    
    return jsonify({
        "telemetry": telemetry_data,
        "lidar": lidar_distances,
        "log_distribution": log_counts,
        "battery": drone_state["battery"]
    })

# Endpoint to fetch coordinates
@app.route("/api/gps_data")
def api_gps_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, lat, lon, alt, quality FROM gps_logs ORDER BY id DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()
    
    points = []
    for row in rows:
        points.append({
            "id": f"#{1000 + row['id']}",
            "lat": row["lat"],
            "lon": row["lon"],
            "alt": f"{row['alt']:.1f}m",
            "acc": "±1.5m" if row["quality"] == "Excellent" else "±3.0m",
            "quality": row["quality"]
        })
    return jsonify(points)

@app.route("/api/generate_gps_points", methods=['POST'])
def api_generate_gps_points():
    data = request.get_json() or {}
    try:
        lat_base = float(data.get('lat'))
        lon_base = float(data.get('lon'))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid or missing coordinates"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    
    drone_state["lat"] = lat_base
    drone_state["lon"] = lon_base
    
    points = []
    for i in range(50):
        lat = lat_base + random.uniform(-0.0006, 0.0006)
        lon = lon_base + random.uniform(-0.0006, 0.0006)
        alt = round(random.uniform(180.0, 210.0), 1)
        quality = random.choice(["Excellent", "Good"])
        
        cursor.execute(
            "INSERT INTO gps_logs (lat, lon, alt, quality, source) VALUES (?, ?, ?, ?, ?)",
            (lat, lon, alt, quality, "Grid Coordinate Scan")
        )
        
        points.append({
            "id": f"#{random.randint(1000, 9999) + i}",
            "lat": lat,
            "lon": lon,
            "alt": f"{alt}m",
            "acc": f"±{random.uniform(1.2, 4.0):.2f}m",
            "quality": quality
        })
        
    cursor.execute("INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
                   ("Position Pathing Agent", "INFO", f"Generated grid scan coordinates around {lat_base:.5f}, {lon_base:.5f}"))
    conn.commit()
    conn.close()
    return jsonify(points)

@app.route('/api/geocode', methods=['POST'])
def geocode():
    data = request.get_json() or {}
    address = data.get('address')
    if not address:
        return jsonify({'error': 'Address is required'}), 400

    url = f"{NOMINATIM_API}/search"
    params = {'q': address, 'format': 'json', 'limit': 1}
    headers = {'User-Agent': 'CommandConsole/1.0 (dev@example.com)'}
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        api_data = response.json()
        if api_data:
            location = api_data[0]
            lat = float(location['lat'])
            lon = float(location['lon'])
            return jsonify({'lat': lat, 'lon': lon})
        else:
            return jsonify({'error': 'Location not found'}), 404
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Geocode query failed: {e}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/surveillance_data")
def api_surveillance_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT type, confidence FROM threat_logs ORDER BY id DESC LIMIT 2")
    rows = cursor.fetchall()
    conn.close()
    
    objects = []
    for r in rows:
        objects.append({
            "type": r["type"],
            "confidence": float(r["confidence"]),
            "x": round(random.uniform(0.1, 0.9), 2),
            "y": round(random.uniform(0.1, 0.9), 2)
        })
    if not objects:
        objects = [
            {"type": "Scanning Coordinates...", "confidence": 0.0, "x": 0.5, "y": 0.5}
        ]
    return jsonify(objects)

@app.route("/api/flight_parameters")
def api_flight_parameters():
    return jsonify({
        "speed": f"{drone_state['speed']:.1f}",
        "altitude": f"{drone_state['alt']:.1f}",
        "heading": f"{drone_state['heading']:.0f}",
        "battery": f"{drone_state['battery']:.1f}",
        "connection": f"{drone_state['connection']}",
        "lat": f"{drone_state['lat']:.6f}",
        "lon": f"{drone_state['lon']:.6f}",
        "mission": drone_state["current_mission"]
    })

# API for log explorer queries
@app.route("/api/logs")
def api_get_logs():
    table = request.args.get("table", "system_logs")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    agent = request.args.get("agent", "")
    level = request.args.get("level", "")
    
    allowed_tables = ["system_logs", "gps_logs", "threat_logs", "obstacle_logs", "telemetry_logs"]
    if table not in allowed_tables:
        return jsonify({"error": "Invalid table name"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = f"SELECT * FROM {table}"
    params = []
    conditions = []
    
    if table == "system_logs":
        if agent:
            conditions.append("agent_name = ?")
            params.append(agent)
        if level:
            conditions.append("log_level = ?")
            params.append(level)
            
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += f" ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    result = [dict(row) for row in rows]
    conn.close()
    return jsonify(result)

# API to save a threat detected by optical sensors
@app.route("/api/threats", methods=["POST"])
def api_log_threat():
    data = request.get_json() or {}
    threat_type = data.get("type", "Visual Target")
    confidence = float(data.get("confidence", 0.8))
    if confidence <= 1.0:
        confidence = int(confidence * 100)
    else:
        confidence = int(confidence)
        
    details = data.get("details", f"Optical registration of {threat_type} in coordinates")
    status = data.get("status", "ACTIVE")
    lat = data.get("lat", drone_state["lat"])
    lon = data.get("lon", drone_state["lon"])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO threat_logs (type, confidence, details, status, lat, lon) VALUES (?, ?, ?, ?, ?, ?)",
        (threat_type, confidence, details, status, lat, lon)
    )
    
    cursor.execute(
        "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
        ("Optical Activity Agent", "WARNING" if threat_type.lower() == "person" else "INFO", 
         f"Activity logged: {threat_type} ({confidence}% confidence) at {lat:.5f}, {lon:.5f}")
    )
    
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

# API to return live obstacle scans
@app.route("/api/obstacles")
def api_get_obstacles():
    points = []
    for i in range(36):
        angle = i * 10
        if drone_state["current_mission"] == "EVADING" and (angle < 45 or angle > 315):
            distance = round(random.uniform(0.6, 1.4), 2)
        else:
            if random.random() < 0.12:
                distance = round(random.uniform(1.5, 5.0), 2)
            else:
                distance = round(random.uniform(8.0, 16.0), 2)
        points.append({"angle": angle, "distance": distance})
    return jsonify(points)

# API for keyboard controls and CLI parser
@app.route("/api/flight_command", methods=["POST"])
def api_flight_command():
    data = request.get_json() or {}
    command_text = data.get("command", "").strip().lower()
    
    if not command_text:
        return jsonify({"error": "No command entered"}), 400
        
    parts = command_text.split()
    base_cmd = parts[0]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    response_msg = ""
    log_msg = ""
    
    if base_cmd == "takeoff":
        drone_state["current_mission"] = "PATROLLING"
        drone_state["speed"] = 10.0
        drone_state["alt"] = 150.0
        response_msg = "Takeoff sequence initiated. Autopilot engaged."
        log_msg = "Manual takeoff command processed. Mission: PATROLLING."
    elif base_cmd == "land":
        drone_state["current_mission"] = "IDLE"
        drone_state["speed"] = 0.0
        drone_state["alt"] = 0.0
        response_msg = "Descent initiated. Safe landing completed."
        log_msg = "Manual land command processed. Mission: IDLE."
    elif base_cmd == "patrol":
        drone_state["current_mission"] = "PATROLLING"
        drone_state["speed"] = 12.0
        response_msg = "Grid patrol course plotted. Drone executing."
        log_msg = "Autonomous patrol mission started."
    elif base_cmd == "evade":
        drone_state["current_mission"] = "EVADING"
        drone_state["heading"] = (drone_state["heading"] + 180) % 360
        response_msg = "Evasive maneuvers triggered. Initiating climb."
        log_msg = "Manual override: Evasive maneuvers activated."
    elif base_cmd == "home":
        drone_state["current_mission"] = "RETURNING"
        response_msg = "Returning to launch pad coordinates."
        log_msg = "Mission updated: Return-to-Home."
    elif base_cmd == "forward":
        drone_state["current_mission"] = "PATROLLING"
        drone_state["speed"] = min(drone_state["speed"] + 2.0, 30.0)
        rad = math.radians(drone_state["heading"])
        drone_state["lat"] += (2.0 * math.cos(rad)) / 111000.0
        drone_state["lon"] += (2.0 * math.sin(rad)) / (111000.0 * math.cos(math.radians(drone_state["lat"])))
        response_msg = f"Accelerating forward. Speed: {drone_state['speed']}m/s"
        log_msg = "Manual Control: Forward throttle applied."
    elif base_cmd == "backward":
        drone_state["speed"] = max(drone_state["speed"] - 2.0, 0.0)
        rad = math.radians(drone_state["heading"])
        drone_state["lat"] -= (2.0 * math.cos(rad)) / 111000.0
        drone_state["lon"] -= (2.0 * math.sin(rad)) / (111000.0 * math.cos(math.radians(drone_state["lat"])))
        response_msg = f"Decelerating. Speed: {drone_state['speed']}m/s"
        log_msg = "Manual Control: Reverse thrust applied."
    elif base_cmd == "left":
        drone_state["heading"] = (drone_state["heading"] - 15) % 360
        response_msg = f"Yaw Left. Heading: {drone_state['heading']}°"
        log_msg = f"Manual Control: Steered left. Heading={drone_state['heading']}°"
    elif base_cmd == "right":
        drone_state["heading"] = (drone_state["heading"] + 15) % 360
        response_msg = f"Yaw Right. Heading: {drone_state['heading']}°"
        log_msg = f"Manual Control: Steered right. Heading={drone_state['heading']}°"
    elif base_cmd == "up":
        drone_state["alt"] = min(drone_state["alt"] + 10.0, 500.0)
        response_msg = f"Climbing. Altitude: {drone_state['alt']}m"
        log_msg = f"Manual Control: Altitude increased to {drone_state['alt']}m"
    elif base_cmd == "down":
        drone_state["alt"] = max(drone_state["alt"] - 10.0, 0.0)
        response_msg = f"Descending. Altitude: {drone_state['alt']}m"
        log_msg = f"Manual Control: Altitude decreased to {drone_state['alt']}m"
    elif base_cmd == "set" and len(parts) >= 3:
        param = parts[1]
        value = parts[2]
        try:
            if param == "altitude":
                drone_state["alt"] = float(value)
                response_msg = f"Altitude adjusted to {value}m."
            elif param == "speed":
                drone_state["speed"] = float(value)
                response_msg = f"Speed adjusted to {value} m/s."
            elif param == "heading":
                drone_state["heading"] = float(value) % 360
                response_msg = f"Heading adjusted to {value}°."
            else:
                return jsonify({"error": f"Unknown set parameter: {param}"}), 400
            log_msg = f"CLI parameter override: Set {param} to {value}."
        except ValueError:
            return jsonify({"error": f"Invalid format for value '{value}'"}), 400
    elif base_cmd == "fly" and len(parts) >= 3:
        try:
            lat = float(parts[1])
            lon = float(parts[2])
            drone_state["lat"] = lat
            drone_state["lon"] = lon
            drone_state["current_mission"] = "PATROLLING"
            response_msg = f"Flight path waypoint locked: {lat:.6f}, {lon:.6f}."
            log_msg = f"CLI routing: Programmed coordinates override to {lat:.6f}, {lon:.6f}."
        except ValueError:
            return jsonify({"error": "Invalid location format. Use: fly [lat] [lon]"}), 400
    else:
        return jsonify({"error": f"Unknown command expression: {command_text}"}), 400
        
    cursor.execute(
        "INSERT INTO system_logs (agent_name, log_level, message) VALUES (?, ?, ?)",
        ("Flight Plan Controller", "INFO", log_msg)
    )
    conn.commit()
    conn.close()
    
    return jsonify({"message": response_msg, "drone_state": drone_state})

# API for exporting database logs to csv/json
@app.route("/api/logs/export")
def api_export_logs():
    table = request.args.get("table", "system_logs")
    fmt = request.args.get("format", "csv")
    
    allowed_tables = ["system_logs", "gps_logs", "threat_logs", "obstacle_logs", "telemetry_logs"]
    if table not in allowed_tables:
        return "Invalid table name", 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table} ORDER BY id DESC")
    rows = cursor.fetchall()
    
    result = [dict(row) for row in rows]
    conn.close()
    
    if fmt == "json":
        return jsonify(result)
    else:
        if not result:
            return "No records found to export.", 404
            
        dest = io.StringIO()
        writer = csv.writer(dest)
        writer.writerow(result[0].keys())
        for row in result:
            writer.writerow(row.values())
            
        response = Response(dest.getvalue(), mimetype="text/csv")
        response.headers.set("Content-Disposition", "attachment", filename=f"operations_{table}.csv")
        return response

if __name__ == "__main__":
    init_db()
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        t = threading.Thread(target=run_agents_loop, daemon=True)
        t.start()
        t_detect = threading.Thread(target=background_detection_loop, daemon=True)
        t_detect.start()
    app.run(debug=True)