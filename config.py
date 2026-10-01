"""
Central Configuration for Wearable Activity Recognition Project.
Supports both HiveMQ Public Broker and HiveMQ Cloud (TLS + Auth).
"""
import os
import ssl
from dotenv import load_dotenv

# Load local .env file if present
load_dotenv()

def sanitize_broker_host(host_str: str) -> str:
    """Strip protocol prefixes and port suffixes from user-provided broker string."""
    if not host_str:
        return "broker.hivemq.com"
    host_str = host_str.strip()
    for prefix in ["mqtts://", "mqtt://", "ssl://", "tls://", "wss://", "ws://", "https://", "http://"]:
        if host_str.startswith(prefix):
            host_str = host_str[len(prefix):]
    if ":" in host_str:
        host_str = host_str.split(":")[0]
    return host_str.strip("/")

# HiveMQ Broker Settings
RAW_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_BROKER = sanitize_broker_host(RAW_BROKER)

# Default to port 8883 if on HiveMQ Cloud, else 1883
default_port = 8883 if "hivemq.cloud" in MQTT_BROKER.lower() else 1883
MQTT_PORT = int(os.getenv("MQTT_PORT", default_port))
MQTT_WS_PORT = int(os.getenv("MQTT_WS_PORT", 8884 if "hivemq.cloud" in MQTT_BROKER.lower() else 8000))
MQTT_KEEPALIVE = 60

# HiveMQ Cloud Authentication (Required for HiveMQ Cloud clusters)
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# TLS / SSL is required for HiveMQ Cloud (Port 8883)
env_tls = os.getenv("MQTT_USE_TLS", "").lower()
if env_tls in ["true", "1", "yes"]:
    MQTT_USE_TLS = True
elif env_tls in ["false", "0", "no"]:
    MQTT_USE_TLS = False
else:
    # Auto-enable TLS if port 8883 or hivemq.cloud domain
    MQTT_USE_TLS = ("hivemq.cloud" in MQTT_BROKER.lower()) or (MQTT_PORT == 8883)

# Topic namespace
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
        "password_hash": "admin123",
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
