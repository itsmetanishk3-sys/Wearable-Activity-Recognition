"""
Synthetic Wearable Telemetry Publisher (Layer 1 to Layer 5).
Simulates real-time MPU6050 6-axis IMU (Accelerometer + Gyroscope) and DHT11
temperature/humidity sensors, publishing JSON packets to HiveMQ MQTT Broker.
"""
import time
import json
import random
import argparse
import sys
from datetime import datetime
import numpy as np
import paho.mqtt.client as mqtt
from config import MQTT_BROKER, MQTT_PORT, MQTT_SENSOR_TOPIC, ACTIVITIES

def generate_telemetry_packet(activity: str, device_id: str = "ESP32_WEARABLE_01") -> dict:
    """Generate realistic physical sensor values for a specified human activity."""
    noise = np.random.normal(0, 0.15, 6)
    
    if activity == "Sitting":
        ax = 0.2 + noise[0] * 0.3
        ay = 0.3 + noise[1] * 0.3
        az = 9.75 + noise[2] * 0.2
        gx = 0.4 + noise[3] * 1.0
        gy = -0.3 + noise[4] * 1.0
        gz = 0.1 + noise[5] * 1.0
        temp = round(float(np.random.normal(36.6, 0.2)), 2)
        hum = round(float(np.random.normal(48.0, 1.5)), 2)

    elif activity == "Standing":
        ax = 0.1 + noise[0] * 0.4
        ay = 0.2 + noise[1] * 0.4
        az = 9.81 + noise[2] * 0.3
        gx = 1.0 + noise[3] * 2.0
        gy = 1.0 + noise[4] * 2.0
        gz = 0.5 + noise[5] * 1.5
        temp = round(float(np.random.normal(36.7, 0.2)), 2)
        hum = round(float(np.random.normal(50.0, 1.5)), 2)

    elif activity == "Walking":
        phase = time.time() * 3.5  # ~1.8 Hz step frequency
        ax = 2.2 * np.sin(phase) + noise[0] * 0.8
        ay = 1.6 * np.cos(phase) + noise[1] * 0.6
        az = 9.8 + 2.5 * np.sin(2 * phase) + noise[2] * 0.8
        gx = 35.0 * np.sin(phase) + noise[3] * 8.0
        gy = 25.0 * np.cos(phase) + noise[4] * 6.0
        gz = 18.0 * np.sin(phase) + noise[5] * 5.0
        temp = round(float(np.random.normal(37.0, 0.3)), 2)
        hum = round(float(np.random.normal(53.0, 2.0)), 2)

    elif activity == "Running":
        phase = time.time() * 6.0  # ~3.0 Hz step frequency
        ax = 5.5 * np.sin(phase) + noise[0] * 1.8
        ay = 4.2 * np.cos(phase) + noise[1] * 1.5
        az = 9.8 + 7.5 * np.sin(2 * phase) + noise[2] * 2.0
        gx = 95.0 * np.sin(phase) + noise[3] * 20.0
        gy = 75.0 * np.cos(phase) + noise[4] * 18.0
        gz = 55.0 * np.sin(phase) + noise[5] * 12.0
        temp = round(float(np.random.normal(37.7, 0.4)), 2)
        hum = round(float(np.random.normal(63.0, 2.5)), 2)

    elif activity == "Jumping":
        is_landing = random.choice([True, False])
        if is_landing:
            ax = float(np.random.normal(1.2, 1.5))
            ay = float(np.random.normal(1.0, 1.2))
            az = float(np.random.normal(22.0, 3.0)) # sharp impact
        else:
            ax = float(np.random.normal(0.4, 0.6))
            ay = float(np.random.normal(0.4, 0.6))
            az = float(np.random.normal(3.0, 1.2)) # free-fall phase
        gx = float(np.random.normal(20.0, 12.0))
        gy = float(np.random.normal(24.0, 15.0))
        gz = float(np.random.normal(15.0, 8.0))
        temp = round(float(np.random.normal(37.3, 0.3)), 2)
        hum = round(float(np.random.normal(57.0, 2.0)), 2)

    elif activity == "Fall Detected":
        # Simulate abrupt fall impact spike
        ax = float(np.random.normal(15.0, 4.0))
        ay = float(np.random.normal(17.0, 5.0))
        az = float(np.random.normal(29.0, 5.0))
        gx = float(np.random.normal(190.0, 35.0))
        gy = float(np.random.normal(165.0, 30.0))
        gz = float(np.random.normal(140.0, 25.0))
        temp = round(float(np.random.normal(36.9, 0.3)), 2)
        hum = round(float(np.random.normal(52.0, 2.0)), 2)
    else:
        ax, ay, az = 0.0, 0.0, 9.8
        gx, gy, gz = 0.0, 0.0, 0.0
        temp, hum = 36.6, 50.0

    return {
        "device_id": device_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ax": round(float(ax), 2),
        "ay": round(float(ay), 2),
        "az": round(float(az), 2),
        "gx": round(float(gx), 2),
        "gy": round(float(gy), 2),
        "gz": round(float(gz), 2),
        "temperature": temp,
        "humidity": hum,
        "simulated_activity": activity
    }

published_count = 0
connected_flag = False

def on_connect(client, userdata, flags, rc, properties=None):
    global connected_flag
    connected_flag = True
    print(f"\n[HIVEMQ SUCCESS] Connected to broker (Result Code: {rc})", flush=True)

def on_disconnect(client, userdata, flags, rc, properties=None):
    global connected_flag
    connected_flag = False
    print(f"\n[HIVEMQ WARNING] Disconnected from broker (RC: {rc}). Reconnecting...", flush=True)

def on_publish(client, userdata, mid, reason_codes=None, properties=None):
    global published_count
    published_count += 1

def main():
    parser = argparse.ArgumentParser(description="Wearable IoT Telemetry Publisher to HiveMQ")
    parser.add_argument("--broker", default=MQTT_BROKER, help="MQTT Broker host")
    parser.add_argument("--port", type=int, default=MQTT_PORT, help="MQTT Port")
    parser.add_argument("--topic", default=MQTT_SENSOR_TOPIC, help="MQTT topic to publish to")
    parser.add_argument("--mode", default="cycle", choices=["cycle", "manual", "random"], help="Telemetry mode")
    parser.add_argument("--activity", default="Walking", choices=ACTIVITIES, help="Manual activity mode")
    parser.add_argument("--interval", type=float, default=1.0, help="Publish interval in seconds (default: 1.0s)")
    parser.add_argument("--device", default="ESP32_WEARABLE_01", help="Device ID")
    parser.add_argument("--save-csv", action="store_true", help="Layer 1: Also log directly to CSV")
    args = parser.parse_args()

    # Windows console UTF-8 safety
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    client_id = f"wearable_pub_{random.randint(1000, 9999)}"
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    else:
        client = mqtt.Client(client_id=client_id)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish
    client.reconnect_delay_set(min_delay=1, max_delay=10)

    print("=" * 70, flush=True)
    print("  [RUNNING] WEARABLE ACTIVITY RECOGNITION - HIVEMQ TELEMETRY PUBLISHER", flush=True)
    print("=" * 70, flush=True)
    print(f"  Broker Host:       {args.broker}:{args.port}", flush=True)
    print(f"  Publish Topic:     {args.topic}", flush=True)
    print(f"  Interval:          {args.interval} second(s)", flush=True)
    print(f"  Mode:              {args.mode}", flush=True)
    print(f"  Web Client Link:   http://www.hivemq.com/demos/websocket-client/", flush=True)
    print("=" * 70, flush=True)

    try:
        client.connect(args.broker, args.port, keepalive=60)
        client.loop_start()
    except Exception as e:
        print(f"[FATAL] Failed to connect to broker {args.broker}:{args.port}: {e}", flush=True)
        return

    csv_file = "layer1_telemetry.csv" if args.save_csv else None
    if csv_file:
        print(f"Layer 1 Enabled: Logging to {csv_file}", flush=True)

    activity_cycle = [
        ("Sitting", 6),
        ("Standing", 5),
        ("Walking", 8),
        ("Running", 6),
        ("Walking", 5),
        ("Fall Detected", 3),
        ("Sitting", 5)
    ]
    cycle_idx = 0
    step_count = 0
    msg_seq = 0

    print("Sending regular messages to HiveMQ now (Press Ctrl+C to stop)...\n", flush=True)

    try:
        while True:
            if args.mode == "manual":
                curr_activity = args.activity
            elif args.mode == "random":
                curr_activity = random.choice(ACTIVITIES)
            else: # cycle
                curr_activity, duration = activity_cycle[cycle_idx]
                step_count += 1
                if step_count >= duration:
                    cycle_idx = (cycle_idx + 1) % len(activity_cycle)
                    step_count = 0

            payload = generate_telemetry_packet(curr_activity, device_id=args.device)
            json_payload = json.dumps(payload)
            msg_seq += 1

            # Publish with QoS 1 to guarantee delivery acknowledgement
            pub_res = client.publish(args.topic, json_payload, qos=1)

            # Layer 1 CSV logging if requested
            if csv_file:
                with open(csv_file, "a") as f:
                    f.write(f"{payload['timestamp']},{payload['device_id']},{payload['ax']},{payload['ay']},{payload['az']},{payload['gx']},{payload['gy']},{payload['gz']},{payload['temperature']},{payload['humidity']},{payload['simulated_activity']}\n")

            accel_mag = np.sqrt(payload['ax']**2 + payload['ay']**2 + payload['az']**2)
            alert_tag = " [ALERT: FALL TRIGGERED]" if curr_activity == "Fall Detected" else ""
            
            print(
                f"[Msg #{msg_seq:04d} | {payload['timestamp']}] "
                f"Act: {curr_activity:<13} | "
                f"|Acc|: {accel_mag:5.1f} m/s2 | "
                f"Temp: {payload['temperature']:4.1f}C | "
                f"Hum: {payload['humidity']:4.1f}% | "
                f"HiveMQ: SENT{alert_tag}",
                flush=True
            )

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nPublisher stopped by user.", flush=True)
    finally:
        client.loop_stop()
        client.disconnect()
        print("Disconnected cleanly from HiveMQ broker.", flush=True)

if __name__ == "__main__":
    main()
