import sys, ssl, json, sqlite3, datetime
import paho.mqtt.client as mqtt

MQTT_BROKER = "10.128.104.30"
MQTT_PORT = 8883
TELEMETRY_TOPIC = "GB-LON-9249/+/+/events/#"
DB_PATH = "telemetry_store.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS udmi_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id TEXT,
            subsystem TEXT,
            device_id TEXT,
            point_name TEXT,
            present_value REAL,
            raw_units TEXT,
            timestamp TEXT
        )
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_device_point_time 
        ON udmi_telemetry (device_id, point_name, timestamp)
    """)
    conn.commit()
    conn.close()

def log_point(site_id, subsys, device_id, point, val, unit, ts):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO udmi_telemetry 
        (site_id, subsystem, device_id, point_name, present_value, raw_units, timestamp) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (site_id, subsys, device_id, point, val, unit, ts))
    conn.commit()
    conn.close()

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"\n[+] Multi-Subsystem Bridge Online: {TELEMETRY_TOPIC}\n")
        client.subscribe(TELEMETRY_TOPIC)
    else:
        print(f"[-] Connection failed with code: {rc}")

def on_message(client, userdata, msg):
    try:
        topic_parts = msg.topic.split("/")
        if len(topic_parts) < 4:
            return

        site_id = topic_parts[0]
        subsys = topic_parts[1]
        device_id = topic_parts[2]

        data = json.loads(msg.payload.decode("utf-8"))
        ts = data.get("timestamp", datetime.datetime.now().isoformat())
        points = data.get("points", {})

        for pt_name, pt_data in points.items():
            if isinstance(pt_data, dict):
                val = pt_data.get("present_value", pt_data.get("value", None))
                unit = pt_data.get("units", "")
            else:
                val = pt_data
                unit = ""

            if val is not None and isinstance(val, (int, float)):
                log_point(site_id, subsys, device_id, pt_name, float(val), unit, ts)
                print(f"[{subsys}] {device_id} -> {pt_name}: {val} {unit}")
    except Exception:
        pass

def main():
    init_db()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="JA-LAPTOP")
    client.on_connect = on_connect
    client.on_message = on_message

    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile="certs/ca.crt")
    context.load_cert_chain(certfile="certs/client.crt", keyfile="certs/client.key")
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    client.tls_set_context(context)
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_forever()

if __name__ == "__main__":
    main()
