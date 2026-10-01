"""
MQTT Telemetry Consumer Service (Layer 2, 3, 4, 5).
Subscribes to HiveMQ broker, processes incoming wearable sensor packets,
runs ML classification via ml_engine, persists data to SQLite, and broadcasts alerts.
"""
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

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[MQTT] Connected successfully to HiveMQ Broker ({MQTT_BROKER}:{MQTT_PORT})")
        client.subscribe(MQTT_SENSOR_TOPIC)
        print(f"[MQTT] Subscribed to topic: {MQTT_SENSOR_TOPIC}")
    else:
        print(f"[MQTT] Connection failed with error code: {rc}")

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
            print(f"\n[ALERT DETECTED] >>> {alert_info['alert_type']} ({alert_info['severity']}): {alert_info['description']}")
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
            client.publish(MQTT_ACTUATOR_TOPIC, json.dumps(actuator_cmd), qos=0)
            client.publish(MQTT_ALERT_TOPIC, json.dumps(alert_info), qos=0)

        print(f"[STORED #{record_id}] {data.get('timestamp')} | Act: {predicted_act:<13} ({confidence*100:.1f}%) | |Acc|: {ml_result['accel_mag']:5.1f} m/s2 | Temp: {data.get('temperature', 0.0):.1f}C")

    except Exception as e:
        print(f"[ERROR] Failed to process message: {e}")

def main():
    client_id = f"wearable_sub_{random.randint(1000, 9999)}"
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    else:
        client = mqtt.Client(client_id=client_id)

    client.on_connect = on_connect
    client.on_message = on_message

    print("=" * 65)
    print("  WEARABLE TELEMETRY MQTT CONSUMER & ML INFERENCE WORKER")
    print("=" * 65)
    print(f"HiveMQ Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Sensor Topic:  {MQTT_SENSOR_TOPIC}")
    print(f"Alert Topic:   {MQTT_ALERT_TOPIC}")
    print(f"Actuator Topic:{MQTT_ACTUATOR_TOPIC}")
    print("=" * 65)

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nConsumer stopped by user.")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
