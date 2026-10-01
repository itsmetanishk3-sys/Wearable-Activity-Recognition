# 🏃 Wearable Activity Recognition & Health Monitoring using ML & IoT

An end-to-end, multi-layered IoT and Edge-AI system for **Human Activity Recognition (HAR)** and emergency fall detection using wearable IMU sensor fusion, HiveMQ MQTT cloud messaging, SQLite relational persistence, and an interactive Streamlit Cloud dashboard with user authentication.

---

## 📋 Architecture & Whiteboard Layer Mapping

This project is built directly to satisfy the 6 progressive architecture layers:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       SYSTEM LAYER PIPELINES                                                 │
├─────────┬────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Layer 1 │ Synthetic Data ➔ MQTT ➔ CSV ➔ Dashboard                                                           │
│ Layer 2 │ Synthetic Data ➔ MQTT ➔ HiveMQ ➔ Dashboard                                                         │
│ Layer 3 │ Synthetic Data ➔ MQTT ➔ HiveMQ ➔ SQLite ➔ Dashboard                                                │
│ Layer 4 │ Synthetic Data ➔ MQTT ➔ HiveMQ ➔ SQLite ➔ Node-RED ➔ Dashboard ➔ Alert                           │
│ Layer 5 │ Synthetic Data ➔ MQTT ➔ HiveMQ ➔ SQLite ➔ Node-RED ➔ AI/ML ➔ Login Page ➔ Dashboard ➔ Alert       │
│ Layer 6 │ Real Sensor (DHT11 & MPU6050) ➔ ESP32 ➔ MQTT ➔ HiveMQ ➔ SQLite ➔ Node-RED ➔ Dashboard ➔ Buzzer/LED │
└─────────┴────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Project Repository Structure

```
d:/Hcl/
├── .streamlit/
│   └── config.toml             # Custom modern dark UI theme for Streamlit
├── esp32/
│   └── wearable_device.ino     # Layer 6: ESP32 + MPU6050 + DHT11 Arduino C++ firmware
├── nodered/
│   └── flows.json              # Layer 4 & 5: Complete importable Node-RED flow JSON
├── models/
│   ├── activity_model.pkl      # Trained Random Forest classifier
│   ├── scaler.pkl              # Feature normalizer
│   ├── label_encoder.pkl       # Target activity encoder
│   ├── model_metadata.json     # Accuracy, feature importance & evaluation metrics
│   └── synthetic_wearable_dataset.csv # Layer 1 CSV dataset
├── app.py                      # Main Streamlit Dashboard with Login & 5 interactive tabs
├── config.py                   # Central MQTT, SQLite, ML, and threshold configurations
├── database.py                 # SQLite database engine (telemetry, alerts, users)
├── ml_engine.py                # Real-time feature calculation & ML inference engine
├── train_model.py              # Synthetic biomechanics generator & model training script
├── synthetic_publisher.py      # Layer 1-5 continuous HiveMQ MQTT publisher
├── mqtt_subscriber.py          # Standalone background consumer & alert worker
├── requirements.txt            # Python dependencies for VS Code & Streamlit Cloud
├── .gitignore                  # Git repository exclusion rules
└── README.md                   # Full system documentation
```

---

## ⚡ Quick Start: Running in VS Code

### 1. Open Project in VS Code
Open VS Code and choose **File > Open Folder...**, then select `d:\Hcl`.

### 2. Install Dependencies
Open a PowerShell or CMD terminal in VS Code:
```bash
python -m pip install -r requirements.txt
```

### 3. Verify / Re-Train the AI Model (Optional)
The repository includes pre-trained model artifacts. You can retrain anytime by running:
```bash
python train_model.py
```
> **Output:** Trains a 100-tree Random Forest classifier achieving **>99.9% accuracy** across 6 activity classes (*Walking, Running, Sitting, Standing, Jumping, Fall Detected*).

### 4. Launch the Streamlit Dashboard
```bash
streamlit run app.py
```
Your default browser will automatically open to `http://localhost:8501`.

---

## 🔐 Dashboard Login Credentials

The portal features a secure authentication gateway (Layer 5 requirement) backed by SQLite:

| Role | Username | Password | Access Description |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | Full system control, telemetry query, database export |
| **Healthcare Monitor** | `doctor` | `doc123` | Patient activity monitoring & emergency fall alerts |
| **IoT Student** | `student` | `student123` | Lab inspection, live charts, and sensor diagnostics |

> **Tip:** You can also click the **"One-Click Demo Access"** buttons on the login screen for instant evaluation without typing passwords!

---

## 📡 Live Telemetry & MQTT Simulation

To test real-time data streaming over HiveMQ, open a **second terminal in VS Code** while the dashboard is running:

### Option A: Continuous Autonomous Cycle Mode
Cycles through Walking ➔ Running ➔ Sitting ➔ Standing ➔ Fall Event:
```bash
python synthetic_publisher.py
```

### Option B: Manual Activity Simulation
Publish a specific activity continuously (e.g. Running):
```bash
python synthetic_publisher.py --mode manual --activity Running --interval 1.0
```

### Option C: Trigger Immediate Fall Alert
```bash
python synthetic_publisher.py --mode manual --activity "Fall Detected" --interval 1.0
```

### Option D: Direct In-App Injector
Inside the Streamlit dashboard sidebar, use the **Quick Telemetry Injector** or **"Simulate Critical Fall Event"** button to inject telemetry directly with zero command-line setup!

---

## 🌐 Deploying to Streamlit Cloud & GitHub

### Step 1: Initialize Git and Commit
In your VS Code terminal inside `d:\Hcl`:
```bash
git init
git add .
git commit -m "Initial commit: Wearable Activity Recognition Layers 1-6"
```

### Step 2: Push to GitHub
1. Create a new repository on [GitHub](https://github.com/new) (e.g., `wearable-activity-recognition-ml`).
2. Link and push your local branch:
```bash
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/wearable-activity-recognition-ml.git
git push -u origin main
```

### Step 3: Deploy on Streamlit Community Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io/) and log in with your GitHub account.
2. Click **New app**.
3. Select your repository: `<YOUR_GITHUB_USERNAME>/wearable-activity-recognition-ml`.
4. Branch: `main`.
5. Main file path: `app.py`.
6. Click **Deploy!**
7. Your app will be live on a public URL accessible from any phone, tablet, or PC worldwide!

---

## 🏗️ Detailed Layer Breakdown

### Layer 1: Synthetic Data ➔ MQTT ➔ CSV ➔ Dashboard
- Run `python synthetic_publisher.py --save-csv` to generate continuous telemetry and record directly to `layer1_telemetry.csv`.
- The dashboard allows one-click export of data to CSV under the **SQLite Telemetry History** tab.

### Layer 2: Synthetic Data ➔ MQTT ➔ HiveMQ ➔ Dashboard
- Uses public broker `broker.hivemq.com:1883` on topic `wearable/activity/iot_lab/sensor`.
- The dashboard features a persistent background thread (`HiveMQSubscriberManager`) that maintains a live socket to HiveMQ.

### Layer 3: Synthetic Data ➔ MQTT ➔ HiveMQ ➔ SQLite ➔ Dashboard
- Database engine: SQLite (`wearable_iot.db`).
- Tables: `sensor_telemetry` (time-series), `alerts` (hazard events), `users` (credentials).
- Interactive filterable data table and statistics on the dashboard.

### Layer 4: Event Processing & Node-RED Flow ➔ Alert
- Import `nodered/flows.json` directly into your local Node-RED instance (`http://localhost:1880`).
- Flow subscribes to HiveMQ, checks acceleration magnitude thresholds, detects falls, and dispatches emergency buzzer commands.
- The Streamlit dashboard includes real-time Web Audio API synthesized buzzer alarms!

### Layer 5: AI/ML Inference ➔ Login Page ➔ Dashboard ➔ Alert
- 10-feature classifier: `[ax, ay, az, gx, gy, gz, accel_mag, gyro_mag, temperature, humidity]`.
- Output: Activity class + confidence percentage + probability distribution.
- Login authentication with SHA-256 password hashing.

### Layer 6: Physical Hardware (ESP32 + MPU6050 + DHT11 + LED + Buzzer)
- Flash `esp32/wearable_device.ino` to an ESP32 using the Arduino IDE.
- Pin Connections:
  - **MPU6050**: `SDA -> GPIO 21`, `SCL -> GPIO 22`
  - **DHT11**: `DATA -> GPIO 4`
  - **Alert LED**: `GPIO 18`
  - **Buzzer**: `GPIO 19`
- Publishes real sensor data to HiveMQ and listens on `wearable/activity/iot_lab/actuator` to buzz physical alerts!

---

## 👨‍💻 Tech Stack
- **Languages:** Python 3, C++ (Arduino/ESP32)
- **Machine Learning:** Scikit-Learn, NumPy, Pandas, Joblib
- **IoT & Protocols:** MQTT (paho-mqtt, PubSubClient), HiveMQ Public Broker
- **Database:** SQLite3
- **Frontend / Cloud:** Streamlit, Streamlit Community Cloud
- **Orchestration:** Node-RED
