"""
Train Machine Learning Model for Wearable Activity Recognition (Layer 5).
Generates biomechanically grounded synthetic training telemetry for MPU6050 + DHT11,
trains a Random Forest Classifier, evaluates accuracy, and exports model artifacts.
"""
import os
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import joblib
from config import MODEL_DIR, MODEL_PATH, LABEL_ENCODER_PATH, SCALER_PATH, ACTIVITIES

os.makedirs(MODEL_DIR, exist_ok=True)

def generate_synthetic_activity_dataset(samples_per_activity: int = 1500, random_seed: int = 42):
    """
    Generate synthetic MPU6050 (3-axis Accel + 3-axis Gyro) and DHT11 (Temp, Hum)
    telemetry replicating realistic human biomechanics for 6 distinct activities:
    Walking, Running, Sitting, Standing, Jumping, Fall Detected.
    """
    np.random.seed(random_seed)
    data_list = []

    for activity in ACTIVITIES:
        for _ in range(samples_per_activity):
            noise = np.random.normal(0, 0.15, 6)
            
            if activity == "Sitting":
                # Static posture: mostly gravity on Z, minimal gyro, room temp
                ax = 0.2 + noise[0] * 0.4
                ay = 0.3 + noise[1] * 0.4
                az = 9.75 + noise[2] * 0.3
                gx = 0.5 + noise[3] * 1.5
                gy = -0.4 + noise[4] * 1.5
                gz = 0.2 + noise[5] * 1.5
                temp = np.random.normal(36.6, 0.3)
                hum = np.random.normal(48.0, 2.0)

            elif activity == "Standing":
                # Upright posture: gravity along Z, small postural sway
                ax = 0.1 + noise[0] * 0.6
                ay = 0.1 + noise[1] * 0.6
                az = 9.81 + noise[2] * 0.5
                gx = 1.0 + noise[3] * 3.0
                gy = 1.2 + noise[4] * 3.0
                gz = 0.8 + noise[5] * 2.5
                temp = np.random.normal(36.7, 0.3)
                hum = np.random.normal(50.0, 2.0)

            elif activity == "Walking":
                # Periodic stepping motion: rhythmic oscillation, moderate gyro rotation
                phase = np.random.uniform(0, 2 * np.pi)
                ax = 2.0 * np.sin(phase) + noise[0] * 1.0
                ay = 1.5 * np.cos(phase) + noise[1] * 0.8
                az = 9.8 + 2.8 * np.sin(2 * phase) + noise[2] * 1.0
                gx = 35.0 * np.sin(phase) + noise[3] * 10.0
                gy = 25.0 * np.cos(phase) + noise[4] * 8.0
                gz = 18.0 * np.sin(phase) + noise[5] * 6.0
                temp = np.random.normal(37.0, 0.4)
                hum = np.random.normal(53.0, 2.5)

            elif activity == "Running":
                # High energy and high acceleration peaks, rapid limb rotation
                phase = np.random.uniform(0, 2 * np.pi)
                ax = 5.5 * np.sin(phase) + noise[0] * 2.0
                ay = 4.0 * np.cos(phase) + noise[1] * 1.8
                az = 9.8 + 7.5 * np.sin(2 * phase) + noise[2] * 2.5
                gx = 90.0 * np.sin(phase) + noise[3] * 25.0
                gy = 70.0 * np.cos(phase) + noise[4] * 20.0
                gz = 50.0 * np.sin(phase) + noise[5] * 15.0
                temp = np.random.normal(37.6, 0.5)
                hum = np.random.normal(62.0, 3.0)

            elif activity == "Jumping":
                # High vertical spikes, significant impact on landing
                flight_phase = np.random.choice([0, 1])
                if flight_phase == 0:
                    # Landing impact
                    ax = np.random.normal(1.0, 1.5)
                    ay = np.random.normal(0.8, 1.2)
                    az = np.random.normal(21.0, 3.5)
                else:
                    # Flight / takeoff
                    ax = np.random.normal(0.5, 0.8)
                    ay = np.random.normal(0.5, 0.8)
                    az = np.random.normal(3.5, 1.5)
                gx = np.random.normal(20.0, 15.0)
                gy = np.random.normal(25.0, 18.0)
                gz = np.random.normal(15.0, 10.0)
                temp = np.random.normal(37.4, 0.4)
                hum = np.random.normal(58.0, 3.0)

            elif activity == "Fall Detected":
                # Fall: violent shock impact spike (> 25 m/s^2) or sudden tilt, high rotation
                stage = np.random.choice(["impact", "collapse", "motionless"])
                if stage == "impact":
                    ax = np.random.normal(14.0, 5.0)
                    ay = np.random.normal(16.0, 6.0)
                    az = np.random.normal(28.0, 6.0)
                    gx = np.random.normal(180.0, 45.0)
                    gy = np.random.normal(160.0, 40.0)
                    gz = np.random.normal(140.0, 35.0)
                elif stage == "collapse":
                    ax = np.random.normal(8.0, 2.5)
                    ay = np.random.normal(7.0, 2.0)
                    az = np.random.normal(2.0, 1.5)
                    gx = np.random.normal(120.0, 30.0)
                    gy = np.random.normal(90.0, 25.0)
                    gz = np.random.normal(80.0, 20.0)
                else: # motionless on ground after fall
                    ax = 8.5 + noise[0] * 0.3 # horizontal tilt
                    ay = 4.2 + noise[1] * 0.3
                    az = 1.5 + noise[2] * 0.3
                    gx = noise[3] * 1.0
                    gy = noise[4] * 1.0
                    gz = noise[5] * 1.0
                temp = np.random.normal(36.8, 0.4)
                hum = np.random.normal(52.0, 2.0)

            accel_mag = float(np.sqrt(ax**2 + ay**2 + az**2))
            gyro_mag = float(np.sqrt(gx**2 + gy**2 + gz**2))

            data_list.append({
                "ax": float(ax),
                "ay": float(ay),
                "az": float(az),
                "gx": float(gx),
                "gy": float(gy),
                "gz": float(gz),
                "accel_mag": accel_mag,
                "gyro_mag": gyro_mag,
                "temperature": float(temp),
                "humidity": float(hum),
                "activity": activity
            })

    return pd.DataFrame(data_list)

def train_and_export():
    """Train Random Forest model and persist artifacts."""
    print("Generating synthetic biomechanical sensor dataset...")
    df = generate_synthetic_activity_dataset(samples_per_activity=2000)
    
    # Save a CSV copy for Layer 1 demonstration
    csv_path = os.path.join(MODEL_DIR, "synthetic_wearable_dataset.csv")
    df.to_csv(csv_path, index=False)
    print(f"Dataset generated ({len(df)} samples) and saved to {csv_path}")

    feature_cols = ["ax", "ay", "az", "gx", "gy", "gz", "accel_mag", "gyro_mag", "temperature", "humidity"]
    X = df[feature_cols]
    y = df["activity"]

    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
    )

    print("Training Random Forest Classifier (Layer 5 AI/ML)...")
    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=16,
        min_samples_split=4,
        random_state=42,
        n_jobs=-1
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, target_names=le.classes_, output_dict=True)
    conf_matrix = confusion_matrix(y_test, y_pred).tolist()

    print(f"\nModel Evaluation:")
    print(f"Overall Accuracy: {acc * 100:.2f}%\n")
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    # Save artifacts
    joblib.dump(clf, MODEL_PATH)
    joblib.dump(le, LABEL_ENCODER_PATH)
    joblib.dump(scaler, SCALER_PATH)

    # Save metadata for dashboard visualization
    metadata = {
        "accuracy": float(acc),
        "classes": le.classes_.tolist(),
        "feature_names": feature_cols,
        "feature_importances": clf.feature_importances_.tolist(),
        "confusion_matrix": conf_matrix,
        "classification_report": report
    }
    with open(os.path.join(MODEL_DIR, "model_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=4)

    print(f"Model and artifacts successfully saved to {MODEL_DIR}")
    return acc

if __name__ == "__main__":
    train_and_export()
