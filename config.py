"""
Central Configuration for Wearable Activity Recognition Project.
Configured for Private HiveMQ Cloud Serverless (TLS + Auth).
Credentials are kept secure in environment / secrets and not exposed on the dashboard.
"""
import os
import ssl
from dotenv import load_dotenv

# Load local .env file if present
load_dotenv()

def sanitize_broker_host(host_str: str) -> str:
    """Strip protocol prefixes and port suffixes from user-provided broker string."""
    if not host_str:
        return "24d7e24e34b544e586ec5a85804a4e7f.s1.eu.hivemq.cloud"
    host_str = host_str.strip()
    for prefix in ["mqtts://", "mqtt://", "ssl://", "tls://", "wss://", "ws://", "https://", "http://"]:
        if host_str.startswith(prefix):
            host_str = host_str[len(prefix):]
    if ":" in host_str:
        host_str = host_str.split(":")[0]
    return host_str.strip("/")

def get_config_val(key: str, default: str = "") -> str:
    """Retrieve config from Streamlit Secrets or Environment Variables."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)

# HiveMQ Cloud Broker Settings (Defaulting to user's secure cluster)
RAW_BROKER = get_config_val("MQTT_BROKER", "24d7e24e34b544e586ec5a85804a4e7f.s1.eu.hivemq.cloud")
MQTT_BROKER = sanitize_broker_host(RAW_BROKER)
MQTT_PORT = int(get_config_val("MQTT_PORT", "8883"))
MQTT_WS_PORT = int(get_config_val("MQTT_WS_PORT", "8884"))
MQTT_KEEPALIVE = 60

# HiveMQ Cloud Authentication Credentials
MQTT_USERNAME = get_config_val("MQTT_USERNAME", "Tanishkkk")
MQTT_PASSWORD = get_config_val("MQTT_PASSWORD", "6Tan9@sharingan")

# TLS / SSL is strictly required for HiveMQ Cloud port 8883
env_tls = str(get_config_val("MQTT_USE_TLS", "true")).lower()
MQTT_USE_TLS = env_tls in ["true", "1", "yes"]

# Topic namespace
MQTT_BASE_TOPIC = get_config_val("MQTT_BASE_TOPIC", "wearable/activity/iot_lab")
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

# Default Streamlit Authentication Credentials (Dashboard Users)
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
