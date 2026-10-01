"""
Central Configuration for Wearable Activity Recognition Project.
Covers MQTT Broker settings (HiveMQ), Database settings, ML parameters, and Alert thresholds.
"""
import os

# MQTT Broker Settings
# HiveMQ Public Broker is free, requires no credentials, and is accessible globally.
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_WS_PORT = int(os.getenv("MQTT_WS_PORT", 8000))  # Websocket port if needed
MQTT_KEEPALIVE = 60

# Topic namespace (use a unique channel prefix to avoid cross-talk on public broker)
MQTT_BASE_TOPIC = os.getenv("MQTT_BASE_TOPIC", "wearable/activity/iot_lab")
MQTT_SENSOR_TOPIC = f"{MQTT_BASE_TOPIC}/sensor"
MQTT_ALERT_TOPIC = f"{MQTT_BASE_TOPIC}/alert"
MQTT_ACTUATOR_TOPIC = f"{MQTT_BASE_TOPIC}/actuator"

# SQLite Database Settings
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wearable_iot.db")

# Machine Learning Model Paths
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "activity_model.pkl")
LABEL_ENCODER_PATH = os.path.join(MODEL_DIR, "label_encoder.pkl")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.pkl")

# Wearable Activity Classes
ACTIVITIES = ["Walking", "Running", "Sitting", "Standing", "Jumping", "Fall Detected"]

# Safety and Alert Thresholds
FALL_ACCEL_THRESHOLD = 24.0  # Total acceleration magnitude peak > 24 m/s^2 (~2.5g)
FALL_POST_IMPACT_THRESHOLD = 3.0 # Low motion right after fall
TEMP_HIGH_ALERT = 38.0       # Elevated body/ambient temperature in deg C
TEMP_LOW_ALERT = 15.0        # Low temperature alert
INACTIVITY_TIMEOUT_SEC = 300 # Sitting alert after 5 minutes

# Default Streamlit Authentication Credentials
DEFAULT_USERS = {
    "admin": {
        "password_hash": "admin123", # Plain for demo / hashed in db
        "role": "Administrator",
        "name": "Prof. Admin"
    },
    "doctor": {
        "password_hash": "doc123",
        "role": "Healthcare Monitor",
        "name": "Dr. Sarah Adams"
    },
    "student": {
        "password_hash": "student123",
        "role": "IoT Student",
        "name": "Wearable Lab User"
    }
}
