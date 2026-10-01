"""
SQLite Database Layer for Wearable Activity Recognition System (Layer 3).
Handles telemetry persistence, alert tracking, user authentication, and export utilities.
"""
import sqlite3
import hashlib
from datetime import datetime
import pandas as pd
from config import DB_FILE, DEFAULT_USERS

def hash_pw(password: str) -> str:
    """Compute SHA-256 hash of password for secure storage."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_connection():
    """Get a thread-safe connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables with appropriate schema and default seed data."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Telemetry table (Layer 3)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        device_id TEXT NOT NULL,
        ax REAL NOT NULL,
        ay REAL NOT NULL,
        az REAL NOT NULL,
        gx REAL NOT NULL,
        gy REAL NOT NULL,
        gz REAL NOT NULL,
        accel_mag REAL NOT NULL,
        gyro_mag REAL NOT NULL,
        temperature REAL NOT NULL,
        humidity REAL NOT NULL,
        predicted_activity TEXT DEFAULT 'Unknown',
        confidence REAL DEFAULT 0.0
    )
    """)

    # 2. Alerts table (Layer 4 & 5)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        device_id TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        description TEXT NOT NULL,
        acknowledged INTEGER DEFAULT 0
    )
    """)

    # 3. Users table (Layer 5 Login)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Seed default users if table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        for uname, udata in DEFAULT_USERS.items():
            cursor.execute(
                "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                (uname, hash_pw(udata["password_hash"]), udata["name"], udata["role"])
            )
    
    conn.commit()
    conn.close()

def insert_telemetry(data: dict) -> int:
    """Insert a single sensor record into SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sensor_telemetry (
            timestamp, device_id, ax, ay, az, gx, gy, gz,
            accel_mag, gyro_mag, temperature, humidity,
            predicted_activity, confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("timestamp", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
        data.get("device_id", "ESP32_WEARABLE_01"),
        data.get("ax", 0.0),
        data.get("ay", 0.0),
        data.get("az", 9.8),
        data.get("gx", 0.0),
        data.get("gy", 0.0),
        data.get("gz", 0.0),
        data.get("accel_mag", 9.8),
        data.get("gyro_mag", 0.0),
        data.get("temperature", 25.0),
        data.get("humidity", 50.0),
        data.get("predicted_activity", "Unknown"),
        data.get("confidence", 0.0)
    ))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id

def insert_alert(device_id: str, alert_type: str, severity: str, description: str):
    """Insert an alert event into SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alerts (timestamp, device_id, alert_type, severity, description, acknowledged)
        VALUES (?, ?, ?, ?, ?, 0)
    """, (
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        device_id,
        alert_type,
        severity,
        description
    ))
    conn.commit()
    conn.close()

def get_recent_telemetry(limit: int = 100) -> pd.DataFrame:
    """Retrieve the most recent telemetry readings as a pandas DataFrame."""
    conn = get_connection()
    query = f"""
        SELECT * FROM sensor_telemetry
        ORDER BY id DESC
        LIMIT {limit}
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    if not df.empty:
        # Reverse so time flows forward
        df = df.iloc[::-1].reset_index(drop=True)
    return df

def get_recent_alerts(limit: int = 20) -> pd.DataFrame:
    """Retrieve latest alert notifications."""
    conn = get_connection()
    query = f"""
        SELECT * FROM alerts
        ORDER BY id DESC
        LIMIT {limit}
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def acknowledge_alert(alert_id: int):
    """Mark an alert as resolved/acknowledged."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()

def authenticate_user(username: str, password: str):
    """Authenticate a user with username and password."""
    conn = get_connection()
    cursor = conn.cursor()
    pw_hash = hash_pw(password)
    cursor.execute(
        "SELECT id, username, full_name, role FROM users WHERE username = ? AND password_hash = ?",
        (username, pw_hash)
    )
    user = cursor.fetchone()
    conn.close()
    if user:
        return {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"]
        }
    return None

def register_user(username: str, password: str, full_name: str, role: str = "User") -> bool:
    """Register a new user account."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            (username, hash_pw(password), full_name, role)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_statistics():
    """Retrieve summary counts for telemetry, activities, and alerts."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM sensor_telemetry")
    total_samples = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged = 0")
    active_alerts = cursor.fetchone()[0]

    cursor.execute("""
        SELECT predicted_activity, COUNT(*) as count 
        FROM sensor_telemetry 
        WHERE predicted_activity != 'Unknown'
        GROUP BY predicted_activity
    """)
    activity_counts = dict(cursor.fetchall())
    
    conn.close()
    return {
        "total_samples": total_samples,
        "active_alerts": active_alerts,
        "activity_counts": activity_counts
    }

# Self-initialize on module load
init_db()
