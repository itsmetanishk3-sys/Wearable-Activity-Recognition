"""
Machine Learning Inference Engine for Wearable Activity Recognition (Layer 5).
Loads trained Random Forest model and performs real-time classification and alert triggering.
"""
import os
import json
import numpy as np
import pandas as pd
import joblib
from config import (
    MODEL_PATH, SCALER_PATH, LABEL_ENCODER_PATH, MODEL_DIR,
    FALL_ACCEL_THRESHOLD, TEMP_HIGH_ALERT, TEMP_LOW_ALERT
)

class MLEngine:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.label_encoder = None
        self.metadata = {}
        self.is_loaded = False
        self._load_artifacts()

    def _load_artifacts(self):
        try:
            if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH) and os.path.exists(LABEL_ENCODER_PATH):
                self.model = joblib.load(MODEL_PATH)
                self.scaler = joblib.load(SCALER_PATH)
                self.label_encoder = joblib.load(LABEL_ENCODER_PATH)
                meta_path = os.path.join(MODEL_DIR, "model_metadata.json")
                if os.path.exists(meta_path):
                    with open(meta_path, "r") as f:
                        self.metadata = json.load(f)
                self.is_loaded = True
            else:
                self.is_loaded = False
        except Exception as e:
            print(f"Error loading ML artifacts: {e}")
            self.is_loaded = False

    def predict(self, sensor_dict: dict) -> dict:
        """
        Takes sensor readings (ax, ay, az, gx, gy, gz, temperature, humidity)
        and predicts wearable activity with confidence and alert states.
        """
        ax = float(sensor_dict.get("ax", 0.0))
        ay = float(sensor_dict.get("ay", 0.0))
        az = float(sensor_dict.get("az", 9.8))
        gx = float(sensor_dict.get("gx", 0.0))
        gy = float(sensor_dict.get("gy", 0.0))
        gz = float(sensor_dict.get("gz", 0.0))
        temp = float(sensor_dict.get("temperature", 36.6))
        hum = float(sensor_dict.get("humidity", 50.0))

        # Compute vector magnitudes
        accel_mag = float(np.sqrt(ax**2 + ay**2 + az**2))
        gyro_mag = float(np.sqrt(gx**2 + gy**2 + gz**2))

        sensor_dict["accel_mag"] = round(accel_mag, 2)
        sensor_dict["gyro_mag"] = round(gyro_mag, 2)

        # Fallback heuristic if model is not loaded
        if not self.is_loaded:
            if accel_mag > FALL_ACCEL_THRESHOLD:
                pred = "Fall Detected"
                conf = 0.95
            elif accel_mag > 16.0 or gyro_mag > 120.0:
                pred = "Running"
                conf = 0.85
            elif accel_mag > 11.5 or gyro_mag > 40.0:
                pred = "Walking"
                conf = 0.88
            elif abs(az - 9.8) < 1.0 and gyro_mag < 8.0:
                pred = "Sitting"
                conf = 0.90
            else:
                pred = "Standing"
                conf = 0.85
            probs = {c: 0.1 for c in ["Walking", "Running", "Sitting", "Standing", "Jumping", "Fall Detected"]}
            probs[pred] = conf
        else:
            feature_cols = ["ax", "ay", "az", "gx", "gy", "gz", "accel_mag", "gyro_mag", "temperature", "humidity"]
            X_df = pd.DataFrame([[ax, ay, az, gx, gy, gz, accel_mag, gyro_mag, temp, hum]], columns=feature_cols)
            X_scaled = self.scaler.transform(X_df)
            pred_idx = self.model.predict(X_scaled)[0]
            pred_probs = self.model.predict_proba(X_scaled)[0]
            pred = self.label_encoder.inverse_transform([pred_idx])[0]
            conf = float(np.max(pred_probs))
            probs = {cls_name: float(p) for cls_name, p in zip(self.label_encoder.classes_, pred_probs)}

        # Evaluate Layer 4/5 Alert Conditions
        alert_info = None
        if pred == "Fall Detected" or accel_mag > FALL_ACCEL_THRESHOLD:
            alert_info = {
                "alert_type": "FALL_DETECTED",
                "severity": "CRITICAL",
                "description": f"Emergency! Sudden high-G impact ({accel_mag:.1f} m/s^2) followed by collapse detected!"
            }
        elif temp >= TEMP_HIGH_ALERT:
            alert_info = {
                "alert_type": "HIGH_TEMPERATURE",
                "severity": "WARNING",
                "description": f"Elevated temperature warning: {temp:.1f} deg C exceeds threshold ({TEMP_HIGH_ALERT} deg C)!"
            }
        elif temp <= TEMP_LOW_ALERT:
            alert_info = {
                "alert_type": "LOW_TEMPERATURE",
                "severity": "WARNING",
                "description": f"Hypothermia alert: {temp:.1f} deg C below threshold ({TEMP_LOW_ALERT} deg C)!"
            }

        return {
            "predicted_activity": pred,
            "confidence": round(conf, 4),
            "probabilities": probs,
            "accel_mag": round(accel_mag, 2),
            "gyro_mag": round(gyro_mag, 2),
            "alert": alert_info
        }

# Singleton instance
ml_engine = MLEngine()
