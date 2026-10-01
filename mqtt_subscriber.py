"""
MQTT Telemetry Consumer Service (Layer 2, 3, 4, 5).
Subscribes to HiveMQ broker, processes incoming wearable sensor packets,
runs ML classification via ml_engine, persists data to SQLite, and broadcasts alerts.
"""
import sys
import json
import random
import time
import paho.mqtt.client as mqtt
from config import (
    MQTT_BROKER, MQTT_PORT, MQTT_SENSOR_TOPIC, MQTT_ALERT_TOPIC,
    MQTT_ACTUATOR_TOPIC
)
from ml_engine import ml_engine
import database

# Windows console UTF-8 safety
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] Connected successfully to HiveMQ Broker ({MQTT_BROKER}:{MQTT_PORT})", flush=True)
    client.subscribe(MQTT_SENSOR_TOPIC, qos=1)
    print(f"[MQTT] Subscribed to topic: {MQTT_SENSOR_TOPIC}", flush=True)

def on_disconnect(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] Disconnected from HiveMQ (RC: {rc}). Reconnecting...", flush=True)

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
        
        # 1. Run Machine Learning Inference (Layer 5)
        ml_result = ml_engine.predict(data)
        predicted_act = ml_result["predicted_activity"]
        confidence = ml_result["confidence"]

        # 2. Enrich telemetry dict
        data["predicted_activity"] = predicted_act
        data["confidence"] = confidence
        data["accel_mag"] = ml_result["accel_mag"]
        data["gyro_mag"] = ml_result["gyro_mag"]

        # 3. Persist to SQLite (Layer 3)
        record_id = database.insert_telemetry(data)

        # 4. Check for Alert & Actuator trigger (Layer 4 & Layer 6)
        alert_info = ml_result.get("alert")
        if alert_info:
            print(f"\n[ALERT DETECTED] >>> {alert_info['alert_type']} ({alert_info['severity']}): {alert_info['description']}", flush=True)
            database.insert_alert(
                device_id=data.get("device_id", "ESP32_WEARABLE_01"),
                alert_type=alert_info["alert_type"],
                severity=alert_info["severity"],
                description=alert_info["description"]
            )
            # Publish actuator control packet back to HiveMQ for ESP32 / Node-RED (LED + Buzzer)
            actuator_cmd = {
                "command": "TRIGGER_ALARM",
                "alert_type": alert_info["alert_type"],
                "led": "ON",
                "buzzer": "ON",
                "timestamp": data.get("timestamp")
            }
            client.publish(MQTT_ACTUATOR_TOPIC, json.dumps(actuator_cmd), qos=1)
            client.publish(MQTT_ALERT_TOPIC, json.dumps(alert_info), qos=1)

        print(
            f"[STORED #{record_id:04d}] {data.get('timestamp')} | "
            f"Act: {predicted_act:<13} ({confidence*100:5.1f}%) | "
            f"|Acc|: {ml_result['accel_mag']:5.1f} m/s2 | "
            f"Temp: {data.get('temperature', 0.0):.1f}C",
            flush=True
        )

    except Exception as e:
        print(f"[ERROR] Failed to process message: {e}", flush=True)

def main():
    client_id = f"wearable_sub_{random.randint(1000, 9999)}"
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    else:
        client = mqtt.Client(client_id=client_id)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)

    print("=" * 70, flush=True)
    print("  [CONSUMER] WEARABLE TELEMETRY MQTT CONSUMER & ML INFERENCE WORKER", flush=True)
    print("=" * 70, flush=True)
    print(f"  Broker:        {MQTT_BROKER}:{MQTT_PORT}", flush=True)
    print(f"  Sensor Topic:  {MQTT_SENSOR_TOPIC}", flush=True)
    print(f"  Alert Topic:   {MQTT_ALERT_TOPIC}", flush=True)
    print(f"  Actuator Topic:{MQTT_ACTUATOR_TOPIC}", flush=True)
    print("=" * 70, flush=True)

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nConsumer stopped by user.", flush=True)
    finally:
        client.disconnect()
        print("Disconnected from HiveMQ broker.", flush=True)

if __name__ == "__main__":
    main()
