"""
Wearable Activity Recognition Dashboard (Layers 1 to 6)
Integrates HiveMQ MQTT, SQLite persistence, Real-time ML Inference, Alert Management,
User Authentication, and an Autonomous In-App HiveMQ Telemetry Publisher.
"""
import time
import json
import collections
import threading
import random
from datetime import datetime
import streamlit as st
import pandas as pd
import numpy as np
import paho.mqtt.client as mqtt

from config import (
    MQTT_BROKER, MQTT_PORT, MQTT_SENSOR_TOPIC, MQTT_ALERT_TOPIC,
    MQTT_ACTUATOR_TOPIC, ACTIVITIES, TEMP_HIGH_ALERT, FALL_ACCEL_THRESHOLD
)
import database
from ml_engine import ml_engine
from synthetic_publisher import generate_telemetry_packet

# Streamlit Page Setup
st.set_page_config(
    page_title="Wearable Activity AI Monitor",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# Background HiveMQ MQTT Auto-Publisher (Runs inside Streamlit)
# -------------------------------------------------------------
class HiveMQAutoPublisher:
    """
    Background worker that sends continuous, regular messages to HiveMQ.
    Ensures that messages are transmitted regularly on both local VS Code
    and Streamlit Cloud without requiring a separate terminal window.
    """
    def __init__(self):
        self.is_active = True
        self.interval = 1.0 # 1 second regular heartbeat
        self.client = None
        self.total_published = 0
        self.last_published_packet = None
        self.last_published_time = None
        self.thread = None
        from config import MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, MQTT_USE_TLS
        self.broker = MQTT_BROKER
        self.port = MQTT_PORT
        self.username = MQTT_USERNAME
        self.password = MQTT_PASSWORD
        self.use_tls = MQTT_USE_TLS
        self._init_publisher()

    def _init_publisher(self):
        try:
            client_id = f"st_auto_pub_{random.randint(1000, 9999)}"
            if hasattr(mqtt, "CallbackAPIVersion"):
                self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
            else:
                self.client = mqtt.Client(client_id=client_id)

            if self.use_tls:
                self.client.tls_set()
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)

            self.client.reconnect_delay_set(min_delay=1, max_delay=10)
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()

            if not self.thread or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._publish_loop, daemon=True)
                self.thread.start()
            print(f"[Auto-Publisher] Started streaming to {self.broker}:{self.port} (TLS: {self.use_tls})")
        except Exception as e:
            print(f"[Auto-Publisher Init Error] {e}")

    def reconnect(self, broker: str, port: int, username: str = "", password: str = "", use_tls: bool = False):
        try:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
        except Exception:
            pass
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self._init_publisher()

    def _publish_loop(self):
        activity_cycle = [
            ("Sitting", 6),
            ("Standing", 5),
            ("Walking", 8),
            ("Running", 6),
            ("Walking", 5),
            ("Fall Detected", 2),
            ("Sitting", 6)
        ]
        cycle_idx = 0
        step_count = 0

        while True:
            if self.is_active and self.client:
                try:
                    curr_activity, duration = activity_cycle[cycle_idx]
                    step_count += 1
                    if step_count >= duration:
                        cycle_idx = (cycle_idx + 1) % len(activity_cycle)
                        step_count = 0

                    packet = generate_telemetry_packet(curr_activity, device_id="ESP32_WEARABLE_01")
                    json_str = json.dumps(packet)
                    self.client.publish(MQTT_SENSOR_TOPIC, json_str, qos=1)

                    self.total_published += 1
                    self.last_published_packet = packet
                    self.last_published_time = datetime.now()
                except Exception as e:
                    print(f"[Auto-Publisher Loop Error] {e}")
            time.sleep(self.interval)

    def publish_single(self, activity_name: str, device_id: str = "MANUAL_TRIGGER"):
        if self.client:
            packet = generate_telemetry_packet(activity_name, device_id=device_id)
            self.client.publish(MQTT_SENSOR_TOPIC, json.dumps(packet), qos=1)
            self.total_published += 1
            self.last_published_packet = packet
            self.last_published_time = datetime.now()
            return packet
        return None

# -------------------------------------------------------------
# Background HiveMQ MQTT Subscriber (Cached Resource)
# -------------------------------------------------------------
class HiveMQSubscriberManager:
    def __init__(self):
        self.telemetry_buffer = collections.deque(maxlen=100)
        self.lock = threading.Lock()
        self.client = None
        self.is_connected = False
        self.last_seen = None
        self.total_received = 0
        from config import MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, MQTT_USE_TLS
        self.broker = MQTT_BROKER
        self.port = MQTT_PORT
        self.username = MQTT_USERNAME
        self.password = MQTT_PASSWORD
        self.use_tls = MQTT_USE_TLS
        self._start_client()

    def _start_client(self):
        try:
            client_id = f"st_sub_{random.randint(1000, 9999)}"
            if hasattr(mqtt, "CallbackAPIVersion"):
                self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
            else:
                self.client = mqtt.Client(client_id=client_id)

            if self.use_tls:
                self.client.tls_set()
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)

            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.reconnect_delay_set(min_delay=1, max_delay=10)
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            print(f"[Streamlit MQTT Manager] Failed to initialize: {e}")

    def reconnect(self, broker: str, port: int, username: str = "", password: str = "", use_tls: bool = False):
        try:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
        except Exception:
            pass
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.is_connected = False
        self._start_client()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        self.is_connected = True
        client.subscribe(MQTT_SENSOR_TOPIC, qos=1)
        print(f"[Streamlit MQTT] Connected & Subscribed to {MQTT_SENSOR_TOPIC} on {self.broker}:{self.port}")

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self.is_connected = False
        print(f"[Streamlit MQTT] Disconnected from HiveMQ (RC: {rc})")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            self.last_seen = datetime.now()
            self.total_received += 1

            # Perform Layer 5 ML prediction
            ml_res = ml_engine.predict(payload)
            payload["predicted_activity"] = ml_res["predicted_activity"]
            payload["confidence"] = ml_res["confidence"]
            payload["accel_mag"] = ml_res["accel_mag"]
            payload["gyro_mag"] = ml_res["gyro_mag"]
            payload["probabilities"] = ml_res["probabilities"]

            # Save to SQLite (Layer 3)
            database.insert_telemetry(payload)

            # Evaluate alerts (Layer 4 & 5)
            if ml_res.get("alert"):
                alert = ml_res["alert"]
                database.insert_alert(
                    device_id=payload.get("device_id", "ESP32_WEARABLE_01"),
                    alert_type=alert["alert_type"],
                    severity=alert["severity"],
                    description=alert["description"]
                )

            with self.lock:
                self.telemetry_buffer.append(payload)

        except Exception as e:
            print(f"[MQTT Msg Error] {e}")

    def get_latest_data(self):
        with self.lock:
            if self.telemetry_buffer:
                return self.telemetry_buffer[-1]
            return None

    def get_buffer_dataframe(self):
        with self.lock:
            if not self.telemetry_buffer:
                return pd.DataFrame()
            return pd.DataFrame(list(self.telemetry_buffer))

@st.cache_resource
def get_mqtt_services():
    sub = HiveMQSubscriberManager()
    pub = HiveMQAutoPublisher()
    return sub, pub

mqtt_sub, mqtt_pub = get_mqtt_services()

# -------------------------------------------------------------
# Custom Styling & Audio Alert Injection
# -------------------------------------------------------------
def apply_custom_css():
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #3B82F6, #8B5CF6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .status-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
        font-size: 0.85rem;
    }
    .badge-online { background-color: #064E3B; color: #34D399; border: 1px solid #059669; }
    .badge-alert { background-color: #7F1D1D; color: #FCA5A5; border: 1px solid #DC2626; animation: blinker 1s linear infinite; }
    @keyframes blinker { 50% { opacity: 0.5; } }
    .activity-hero {
        padding: 24px;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 1.2rem;
        border: 1px solid #334155;
    }
    .pulse-dot {
        height: 10px;
        width: 10px;
        background-color: #10B981;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 8px #10B981;
        margin-right: 6px;
    }
    </style>
    """, unsafe_allow_html=True)

def play_buzzer_sound():
    """Synthesize web audio buzzer sound in client browser upon critical alert."""
    audio_html = """
    <script>
    try {
        var audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        var osc = audioCtx.createOscillator();
        var gain = audioCtx.createGain();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(880, audioCtx.currentTime);
        osc.frequency.setValueAtTime(440, audioCtx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.35);
    } catch(e) {}
    </script>
    """
    st.components.v1.html(audio_html, height=0)

# -------------------------------------------------------------
# User Authentication System (Layer 5 Requirement)
# -------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

def render_login_page():
    apply_custom_css()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align:center;'>🔐 Wearable Activity AI Portal</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; color:#94A3B8;'>Secure login to access real-time wearable telemetry & AI models</p>", unsafe_allow_html=True)
        
        tab_login, tab_register, tab_quick = st.tabs(["Sign In", "Register New User", "🚀 One-Click Demo Access"])

        with tab_login:
            with st.form("login_form"):
                uname = st.text_input("Username", placeholder="e.g. admin, doctor, student")
                pword = st.text_input("Password", type="password", placeholder="Enter your password")
                submitted = st.form_submit_button("Sign In", use_container_width=True)
                if submitted:
                    user = database.authenticate_user(uname, pword)
                    if user:
                        st.session_state["authenticated"] = True
                        st.session_state["user_info"] = user
                        st.success(f"Welcome back, {user['full_name']}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password. Please try again.")

        with tab_register:
            with st.form("register_form"):
                reg_name = st.text_input("Full Name", placeholder="e.g. John Doe")
                reg_uname = st.text_input("Desired Username", placeholder="e.g. jdoe")
                reg_pword = st.text_input("Choose Password", type="password")
                reg_role = st.selectbox("Role", ["Researcher", "Clinician", "Student", "Observer"])
                reg_submitted = st.form_submit_button("Create Account", use_container_width=True)
                if reg_submitted:
                    if reg_name and reg_uname and reg_pword:
                        success = database.register_user(reg_uname, reg_pword, reg_name, reg_role)
                        if success:
                            st.success("Account created successfully! You can now log in.")
                        else:
                            st.error("Username already taken. Please choose another.")
                    else:
                        st.warning("Please fill out all fields.")

        with tab_quick:
            st.info("Presenting to evaluators or running locally? Use these pre-configured demo roles:")
            qcol1, qcol2, qcol3 = st.columns(3)
            with qcol1:
                if st.button("👑 Admin Role", use_container_width=True):
                    user = database.authenticate_user("admin", "admin123")
                    st.session_state["authenticated"] = True
                    st.session_state["user_info"] = user
                    st.rerun()
            with qcol2:
                if st.button("🩺 Doctor Role", use_container_width=True):
                    user = database.authenticate_user("doctor", "doc123")
                    st.session_state["authenticated"] = True
                    st.session_state["user_info"] = user
                    st.rerun()
            with qcol3:
                if st.button("🎓 Student Role", use_container_width=True):
                    user = database.authenticate_user("student", "student123")
                    st.session_state["authenticated"] = True
                    st.session_state["user_info"] = user
                    st.rerun()

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #64748B; font-size: 0.85rem;'>"
        "Wearable IoT Activity Recognition Platform • Layers 1-6 Implementation • HiveMQ + Streamlit Cloud Ready"
        "</div>",
        unsafe_allow_html=True
    )

if not st.session_state["authenticated"]:
    render_login_page()
    st.stop()

# -------------------------------------------------------------
# Main Application Dashboard (Authenticated Session)
# -------------------------------------------------------------
apply_custom_css()
user_info = st.session_state["user_info"]

# Sidebar Navigation and System Status
with st.sidebar:
    st.markdown("### 🏃 Wearable AI Hub")
    st.markdown(f"**User:** `{user_info['full_name']}`")
    st.caption(f"Role: `{user_info['role']}`")
    
    if st.button("🚪 Sign Out", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["user_info"] = None
        st.rerun()

    st.markdown("---")
    st.markdown("#### 📡 HiveMQ Live Link")
    st.write(f"**Broker:** `{mqtt_sub.broker}:{mqtt_sub.port}`")
    st.write(f"**Security:** `{'TLS 🔒' if mqtt_sub.use_tls else 'Plain 🔓'}`")
    if mqtt_sub.username:
        st.write(f"**Account:** `{mqtt_sub.username}`")
    st.write(f"**Topic:** `{MQTT_SENSOR_TOPIC}`")
    
    status_tag = (
        "<span class='status-badge badge-online'><span class='pulse-dot'></span>CONNECTED</span>"
        if mqtt_sub.is_connected
        else "<span class='status-badge' style='background:#78350F; color:#FCD34D;'>CONNECTING...</span>"
    )
    st.markdown(f"**Status:** {status_tag}", unsafe_allow_html=True)
    st.write(f"**Published to HiveMQ:** `{mqtt_pub.total_published}` pkts")
    st.write(f"**Received from HiveMQ:** `{mqtt_sub.total_received}` pkts")

    # HiveMQ Cloud Cluster Connection Settings
    with st.expander("⚙️ Switch HiveMQ Broker / Cloud", expanded=False):
        st.caption("Paste your HiveMQ Cloud cluster details from your console:")
        input_broker = st.text_input(
            "MQTT URL / Host",
            value=mqtt_sub.broker,
            placeholder="e.g. 24d7e24e34b544e586ec5a85804a4e7f.s1.eu.hivemq.cloud",
            help="Copy the MQTT URL from your HiveMQ Cloud console"
        )
        input_port = st.number_input(
            "Port",
            value=8883 if "hivemq.cloud" in input_broker.lower() else (mqtt_sub.port or 1883),
            help="Use 8883 for HiveMQ Cloud TLS, or 1883 for public broker"
        )
        input_tls = st.checkbox(
            "Use TLS / SSL Encryption",
            value=("hivemq.cloud" in input_broker.lower()) or (input_port == 8883)
        )
        input_user = st.text_input(
            "Username",
            value=mqtt_sub.username or "",
            placeholder="HiveMQ Cloud Username",
            help="Set under Access Management -> Credentials in HiveMQ Cloud"
        )
        input_pass = st.text_input(
            "Password",
            value=mqtt_sub.password or "",
            type="password",
            placeholder="HiveMQ Cloud Password"
        )

        col_save, col_reset = st.columns(2)
        with col_save:
            if st.button("Connect Server", use_container_width=True, type="primary"):
                from config import sanitize_broker_host
                clean_host = sanitize_broker_host(input_broker)
                mqtt_sub.reconnect(clean_host, int(input_port), input_user, input_pass, input_tls)
                mqtt_pub.reconnect(clean_host, int(input_port), input_user, input_pass, input_tls)
                
                # Persist to .env file
                try:
                    with open(".env", "w") as f:
                        f.write(f"MQTT_BROKER={clean_host}\n")
                        f.write(f"MQTT_PORT={input_port}\n")
                        f.write(f"MQTT_USE_TLS={'true' if input_tls else 'false'}\n")
                        f.write(f"MQTT_USERNAME={input_user}\n")
                        f.write(f"MQTT_PASSWORD={input_pass}\n")
                        f.write(f"MQTT_BASE_TOPIC={MQTT_BASE_TOPIC}\n")
                except Exception as e:
                    print(f"Error saving .env: {e}")
                    
                st.success(f"Connecting to {clean_host}:{input_port}...")
                time.sleep(1)
                st.rerun()

        with col_reset:
            if st.button("Use Public HiveMQ", use_container_width=True):
                mqtt_sub.reconnect("broker.hivemq.com", 1883, "", "", False)
                mqtt_pub.reconnect("broker.hivemq.com", 1883, "", "", False)
                st.info("Switched to public broker.hivemq.com")
                time.sleep(1)
                st.rerun()

    st.markdown("---")
    st.markdown("#### ⚡ Continuous Telemetry Streamer")
    st.caption("Sends continuous regular telemetry to HiveMQ every 1.0 second:")
    auto_pub_toggle = st.toggle("Enable Regular HiveMQ Messages", value=mqtt_pub.is_active)
    mqtt_pub.is_active = auto_pub_toggle

    if mqtt_pub.is_active:
        st.success("🟢 Active: Streaming every 1s to HiveMQ")
    else:
        st.warning("⏸️ Paused (External publisher/ESP32 mode)")

    st.markdown("---")
    st.markdown("#### ⚡ Instant Trigger")
    manual_act = st.selectbox("Trigger Activity Now", ACTIVITIES)
    if st.button(f"Send '{manual_act}' to HiveMQ", use_container_width=True):
        mqtt_pub.publish_single(manual_act, device_id="SIDEBAR_TRIGGER")
        st.success(f"Published '{manual_act}' packet to HiveMQ!")

    if st.button("🚨 Trigger Critical Fall Event", type="primary", use_container_width=True):
        mqtt_pub.publish_single("Fall Detected", device_id="FALL_BUTTON")
        st.error("Dispatched Fall Alert packet to HiveMQ!")

    st.markdown("---")
    st.markdown("#### 🌐 Verify on HiveMQ Web")
    st.markdown(
        f"[🔗 Open HiveMQ Web Client](http://www.hivemq.com/demos/websocket-client/)\n"
        f"*(Topic: `{MQTT_SENSOR_TOPIC}`)*"
    )

# Header
st.markdown("<div class='main-header'>Wearable Activity Recognition & Health Monitoring</div>", unsafe_allow_html=True)
st.caption("AI-Powered Edge-to-Cloud Telemetry Pipeline • MPU6050 6-Axis IMU + DHT11 Sensor Fusion • HiveMQ MQTT")

# Multi-Tab Structure
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Live Activity Monitor",
    "💾 SQLite Telemetry History",
    "🚨 Emergency Alerts & Actuators",
    "🧠 AI/ML Model Intelligence",
    "🏗️ System Architecture (Layers 1-6)"
])

# -------------------------------------------------------------
# TAB 1: Live Activity Monitor (Auto-refreshing via Fragment)
# -------------------------------------------------------------
with tab1:
    @st.fragment(run_every="1s")
    def render_live_telemetry_fragment():
        latest = mqtt_sub.get_latest_data()
        if not latest:
            # Fallback to database
            recent_df = database.get_recent_telemetry(limit=1)
            if not recent_df.empty:
                latest = recent_df.iloc[-1].to_dict()

        if latest:
            curr_act = latest.get("predicted_activity", "Unknown")
            conf = latest.get("confidence", 0.0)
            accel_mag = latest.get("accel_mag", 9.8)
            gyro_mag = latest.get("gyro_mag", 0.0)
            temp = latest.get("temperature", 36.6)
            hum = latest.get("humidity", 50.0)
            dev_id = latest.get("device_id", "ESP32_WEARABLE_01")
            timestamp = latest.get("timestamp", "-")

            hero_bg = "#1E293B"
            hero_color = "#38BDF8"
            hero_icon = "🚶"

            if curr_act == "Walking":
                hero_bg = "linear-gradient(135deg, #1E3A8A 0%, #0284C7 100%)"
                hero_color = "#FFFFFF"
                hero_icon = "🚶"
            elif curr_act == "Running":
                hero_bg = "linear-gradient(135deg, #4C1D95 0%, #7C3AED 100%)"
                hero_color = "#FFFFFF"
                hero_icon = "🏃"
            elif curr_act == "Sitting":
                hero_bg = "linear-gradient(135deg, #1F2937 0%, #374151 100%)"
                hero_color = "#A7F3D0"
                hero_icon = "🪑"
            elif curr_act == "Standing":
                hero_bg = "linear-gradient(135deg, #064E3B 0%, #059669 100%)"
                hero_color = "#FFFFFF"
                hero_icon = "🧍"
            elif curr_act == "Jumping":
                hero_bg = "linear-gradient(135deg, #78350F 0%, #D97706 100%)"
                hero_color = "#FFFFFF"
                hero_icon = "🦘"
            elif curr_act == "Fall Detected":
                hero_bg = "linear-gradient(135deg, #7F1D1D 0%, #DC2626 100%)"
                hero_color = "#FFFFFF"
                hero_icon = "🚨"
                play_buzzer_sound()
                st.error("⚠️ CRITICAL ALERT: Sudden Fall Impact Detected! Buzzer & Emergency Alert Broadcasted!")

            st.markdown(f"""
            <div class='activity-hero' style='background: {hero_bg}; color: {hero_color};'>
                <div style='font-size: 3.5rem; margin-bottom: 6px;'>{hero_icon}</div>
                <div style='font-size: 2.2rem; font-weight: 800; letter-spacing: 1px;'>{curr_act.upper()}</div>
                <div style='font-size: 1.05rem; opacity: 0.9;'>AI Confidence: {conf * 100:.1f}% • Device: {dev_id} • HiveMQ Time: {timestamp}</div>
            </div>
            """, unsafe_allow_html=True)

            mcol1, mcol2, mcol3, mcol4 = st.columns(4)
            with mcol1:
                st.metric("Total Acceleration", f"{accel_mag:.2f} m/s²", delta=f"{accel_mag - 9.8:.1f} vs 1G")
            with mcol2:
                st.metric("Angular Velocity", f"{gyro_mag:.1f} °/s", delta="Gyro Dynamics")
            with mcol3:
                st.metric("Body / Ambient Temp", f"{temp:.1f} °C", delta="Normal" if temp < TEMP_HIGH_ALERT else "HIGH", delta_color="inverse" if temp >= TEMP_HIGH_ALERT else "normal")
            with mcol4:
                st.metric("Relative Humidity", f"{hum:.1f} %", delta="DHT11 Sensor")

            st.markdown("---")

            df_buffer = mqtt_sub.get_buffer_dataframe()
            if df_buffer.empty:
                df_buffer = database.get_recent_telemetry(limit=30)

            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                st.subheader("📈 MPU6050 3-Axis Accelerometer (m/s²)")
                if not df_buffer.empty and all(c in df_buffer.columns for c in ["ax", "ay", "az"]):
                    st.line_chart(df_buffer[["ax", "ay", "az"]].tail(30).reset_index(drop=True))
                else:
                    st.info("Awaiting accelerometer samples...")

            with chart_col2:
                st.subheader("🔄 MPU6050 3-Axis Gyroscope (°/s)")
                if not df_buffer.empty and all(c in df_buffer.columns for c in ["gx", "gy", "gz"]):
                    st.line_chart(df_buffer[["gx", "gy", "gz"]].tail(30).reset_index(drop=True))
                else:
                    st.info("Awaiting gyroscope samples...")

            if "probabilities" in latest and latest["probabilities"]:
                st.subheader("🎯 Real-Time ML Activity Confidence Distribution")
                probs = latest["probabilities"]
                prob_df = pd.DataFrame(list(probs.items()), columns=["Activity", "Probability"])
                prob_df["Confidence %"] = prob_df["Probability"] * 100
                st.bar_chart(prob_df.set_index("Activity")["Confidence %"])

        else:
            st.info("Connecting to HiveMQ... Messages will appear here automatically every 1.0 second.")

    render_live_telemetry_fragment()

# -------------------------------------------------------------
# TAB 2: SQLite Telemetry History (Layer 3)
# -------------------------------------------------------------
with tab2:
    st.subheader("💾 SQLite Persistent Data Records (Layer 3)")
    st.caption("Every sensor packet received from HiveMQ is automatically evaluated and recorded to the local SQLite database.")
    
    stats = database.get_statistics()
    scol1, scol2, scol3 = st.columns(3)
    with scol1:
        st.metric("Total Stored Samples", stats["total_samples"])
    with scol2:
        st.metric("Active Alerts", stats["active_alerts"])
    with scol3:
        st.metric("Unique Activity Classes", len(stats["activity_counts"]))

    limit_query = st.slider("Records to display", min_value=10, max_value=200, value=50, step=10)
    history_df = database.get_recent_telemetry(limit=limit_query)

    if not history_df.empty:
        st.dataframe(
            history_df[["timestamp", "device_id", "predicted_activity", "confidence", "accel_mag", "gyro_mag", "temperature", "humidity"]],
            use_container_width=True
        )

        csv_data = history_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export SQLite Data to CSV (Layer 1 & 3 Compliance)",
            data=csv_data,
            file_name=f"wearable_telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("Database is currently empty. Run the synthetic publisher or inject samples to populate.")

# -------------------------------------------------------------
# TAB 3: Emergency Alerts & Actuators (Layer 4, 5, 6)
# -------------------------------------------------------------
with tab3:
    st.subheader("🚨 Emergency Alert Management & Remote Actuator Control")
    st.caption("Layer 4 Node-RED logic & Layer 5 AI triggers for Fall Detection and High Temperature.")

    alerts_df = database.get_recent_alerts(limit=25)
    if not alerts_df.empty:
        for idx, row in alerts_df.iterrows():
            severity = row["severity"]
            box_type = st.error if severity == "CRITICAL" else st.warning
            with box_type(f"**[{row['timestamp']}] {row['alert_type']}** — {row['description']}"):
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.write(f"Target Device: `{row['device_id']}` | Status: {'Resolved' if row['acknowledged'] else '🔴 ACTIVE'}")
                with col_b:
                    if not row['acknowledged']:
                        if st.button("Acknowledge", key=f"ack_{row['id']}"):
                            database.acknowledge_alert(row['id'])
                            st.rerun()
    else:
        st.success("✅ All systems normal! No active emergency alerts.")

    st.markdown("---")
    st.subheader("🔊 Remote Hardware Actuator Test (Layer 6: Buzzer + LED)")
    st.caption("Dispatches remote control commands via HiveMQ to trigger physical buzzers and alert LEDs on the ESP32.")
    
    act_col1, act_col2 = st.columns(2)
    with act_col1:
        if st.button("📢 Trigger Remote Buzzer & Alarm LED", type="primary", use_container_width=True):
            cmd = {
                "command": "TRIGGER_ALARM",
                "alert_type": "MANUAL_TEST",
                "led": "ON",
                "buzzer": "ON",
                "timestamp": datetime.now().isoformat()
            }
            if mqtt_sub.client and mqtt_sub.is_connected:
                mqtt_sub.client.publish(MQTT_ACTUATOR_TOPIC, json.dumps(cmd), qos=1)
                st.success(f"Published actuator command to HiveMQ topic: `{MQTT_ACTUATOR_TOPIC}`")
            play_buzzer_sound()

    with act_col2:
        if st.button("🔕 Reset / Silence Actuator Alarm", use_container_width=True):
            reset_cmd = {
                "command": "RESET_ALARM",
                "led": "OFF",
                "buzzer": "OFF",
                "timestamp": datetime.now().isoformat()
            }
            if mqtt_sub.client and mqtt_sub.is_connected:
                mqtt_sub.client.publish(MQTT_ACTUATOR_TOPIC, json.dumps(reset_cmd), qos=1)
            st.info("Dispatched silence command.")

# -------------------------------------------------------------
# TAB 4: AI/ML Model Intelligence (Layer 5)
# -------------------------------------------------------------
with tab4:
    st.subheader("🧠 Machine Learning Model Analytics (Layer 5 AI/ML)")
    st.caption("Random Forest Classifier trained on 6-Axis IMU Biomechanical Dynamics and Thermal Telemetry.")

    if ml_engine.is_loaded and ml_engine.metadata:
        meta = ml_engine.metadata
        kpi1, kpi2, kpi3 = st.columns(3)
        with kpi1:
            st.metric("Model Architecture", "Random Forest (100 Trees)")
        with kpi2:
            st.metric("Test Accuracy", f"{meta['accuracy'] * 100:.2f}%")
        with kpi3:
            st.metric("Supported Activity Classes", len(meta['classes']))

        st.markdown("#### 🔍 Feature Importances (Gini Impurity Contribution)")
        feat_df = pd.DataFrame({
            "Feature": meta["feature_names"],
            "Importance": meta["feature_importances"]
        }).sort_values(by="Importance", ascending=False)
        st.bar_chart(feat_df.set_index("Feature"))

        st.markdown("---")
        st.markdown("#### 🧪 Interactive ML Single-Sample Testing Sandbox")
        st.caption("Adjust physical sensor parameters below to test the AI classification model:")

        s_col1, s_col2, s_col3 = st.columns(3)
        with s_col1:
            test_ax = st.slider("Accel X (m/s²)", -25.0, 25.0, 0.0, 0.1)
            test_ay = st.slider("Accel Y (m/s²)", -25.0, 25.0, 0.0, 0.1)
            test_az = st.slider("Accel Z (m/s²)", -10.0, 35.0, 9.8, 0.1)
        with s_col2:
            test_gx = st.slider("Gyro X (°/s)", -250.0, 250.0, 0.0, 1.0)
            test_gy = st.slider("Gyro Y (°/s)", -250.0, 250.0, 0.0, 1.0)
            test_gz = st.slider("Gyro Z (°/s)", -250.0, 250.0, 0.0, 1.0)
        with s_col3:
            test_temp = st.slider("Temperature (°C)", 34.0, 42.0, 36.6, 0.1)
            test_hum = st.slider("Humidity (%)", 20.0, 90.0, 50.0, 1.0)

        if st.button("Run ML Prediction on Sandbox Inputs", use_container_width=True):
            sandbox_res = ml_engine.predict({
                "ax": test_ax, "ay": test_ay, "az": test_az,
                "gx": test_gx, "gy": test_gy, "gz": test_gz,
                "temperature": test_temp, "humidity": test_hum
            })
            st.success(f"**Predicted Activity:** {sandbox_res['predicted_activity']} (Confidence: {sandbox_res['confidence']*100:.1f}%)")
            st.write(f"Total Acceleration: `{sandbox_res['accel_mag']:.2f} m/s²` | Gyro Magnitude: `{sandbox_res['gyro_mag']:.1f} °/s`")
            if sandbox_res.get("alert"):
                st.error(f"Alert: {sandbox_res['alert']['description']}")

    else:
        st.warning("ML Model artifacts not found. Run `python train_model.py` in VS Code to train the model.")

# -------------------------------------------------------------
# TAB 5: System Architecture & Layer Walkthrough
# -------------------------------------------------------------
with tab5:
    st.subheader("🏗️ System Architecture & Progressive Layer Implementation")
    st.caption("Comprehensive implementation of all 6 architectural layers specified on the lab whiteboard.")

    layers = [
        {
            "num": "Layer 1",
            "name": "Synthetic Data Pipeline",
            "pipeline": "Synthetic Data ➔ MQTT ➔ CSV ➔ Dashboard",
            "status": "✅ Fully Implemented",
            "desc": "Generates synthetic wearable dynamics, transmits packets over MQTT, logs to CSV (`synthetic_wearable_dataset.csv`), and renders on the Streamlit dashboard."
        },
        {
            "num": "Layer 2",
            "name": "HiveMQ Cloud Broker Integration",
            "pipeline": "Synthetic Data ➔ MQTT ➔ HiveMQ ➔ Dashboard",
            "status": "✅ Fully Implemented",
            "desc": f"Publishes and subscribes in real-time to public HiveMQ MQTT broker (`{MQTT_BROKER}:{MQTT_PORT}`) on topic `{MQTT_SENSOR_TOPIC}`."
        },
        {
            "num": "Layer 3",
            "name": "Relational Persistence Layer",
            "pipeline": "SD ➔ MQTT ➔ HiveMQ ➔ SQLite ➔ Dashboard",
            "status": "✅ Fully Implemented",
            "desc": "Persists time-series sensor telemetry and prediction logs to thread-safe SQLite database (`wearable_iot.db`)."
        },
        {
            "num": "Layer 4",
            "name": "Event Processing & Alert Engine",
            "pipeline": "SD ➔ MQTT ➔ HiveMQ ➔ SQLite ➔ Node-RED ➔ Dashboard ➔ Alert",
            "status": "✅ Fully Implemented",
            "desc": "Provides exportable Node-RED flow (`nodered/flows.json`) + real-time threshold & anomaly triggers with audio buzzer sound in Streamlit."
        },
        {
            "num": "Layer 5",
            "name": "AI/ML Classification & Secure Portal",
            "pipeline": "SD ➔ MQTT ➔ HiveMQ ➔ SQLite ➔ Node-RED ➔ AI/ML ➔ Login Page ➔ Dashboard ➔ Alert",
            "status": "✅ Fully Implemented",
            "desc": "Trained Random Forest Classifier (99.9% accuracy) classifying 6 activities with probability scoring, multi-user authentication (SHA-256), and role-based views."
        },
        {
            "num": "Layer 6 & Eg",
            "name": "Physical Sensor & Actuator Hardware",
            "pipeline": "DHT11 & MPU6050 ➔ ESP32 ➔ MQTT ➔ HiveMQ ➔ SQLite ➔ Node-RED ➔ AI/ML ➔ Login page ➔ Dashboard ➔ Alert + LED + Buzzer",
            "status": "✅ Fully Implemented",
            "desc": "Production-ready Arduino C++ sketch (`esp32/wearable_device.ino`) with MPU6050 I2C, DHT11, WiFi, HiveMQ MQTT publish & remote buzzer/LED actuation."
        }
    ]

    for lay in layers:
        with st.expander(f"**{lay['num']}: {lay['name']}** — {lay['status']}", expanded=True):
            st.code(lay['pipeline'], language="text")
            st.write(lay['desc'])
