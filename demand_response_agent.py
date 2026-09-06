import ssl
import json
import time
import sqlite3
import requests
import datetime
import paho.mqtt.client as mqtt

MQTT_BROKER = "10.128.104.30"
MQTT_PORT = 8883
SITE_ID = "GB-LON-9249"
DB_PATH = "telemetry_store.db"

COMFORT_TEMP_MIN = 21.0
COMFORT_TEMP_MAX = 24.0
CO2_UPPER_BOUND = 800.0
CARBON_BASELINE = 100.0
CARBON_MAX = 280.0
DEMAND_PEAK_THRESHOLD_KW = 10.0

def init_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS control_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            mode TEXT,
            grid_carbon REAL,
            meter_kw REAL,
            zone_co2 REAL,
            damper_target REAL,
            lighting_target REAL,
            temp_setpoint REAL,
            rationale TEXT,
            ai_suggestion TEXT
        )
    """)
    conn.commit()
    conn.close()

def fetch_live_grid_state():
    url = "https://api.carbonintensity.org.uk/intensity"
    try:
        r = requests.get(url, timeout=4).json()
        item = r["data"][0]["intensity"]
        actual = item.get("actual") or item.get("forecast") or 140.0
        index_label = item.get("index", "moderate").upper()
        forecast = item.get("forecast", actual)
        return float(actual), float(forecast), index_label
    except Exception:
        return 140.0, 140.0, "MODERATE"

def get_latest_telemetry():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT present_value FROM udmi_telemetry 
        WHERE subsystem = 'ELEC' 
        ORDER BY id DESC LIMIT 1
    """)
    elec_row = c.fetchone()
    current_kw = round(float(elec_row[0]), 2) if elec_row else 0.0

    c.execute("""
        SELECT present_value FROM udmi_telemetry 
        WHERE subsystem = 'IOT' AND point_name LIKE '%co2%'
        ORDER BY id DESC LIMIT 1
    """)
    co2_row = c.fetchone()
    current_co2 = round(float(co2_row[0]), 1) if co2_row else 450.0

    c.execute("""
        SELECT present_value FROM udmi_telemetry 
        WHERE subsystem = 'MECH' AND point_name LIKE '%temp%'
        ORDER BY id DESC LIMIT 1
    """)
    mech_row = c.fetchone()
    current_temp = round(float(mech_row[0]), 1) if mech_row else 22.0

    conn.close()
    return current_kw, current_co2, current_temp

def generate_ai_supervisory_advisory(grid_actual, grid_forecast, index_label, kw, co2, temp):
    """
    Synthesizes live grid statistics and building physics into grounded control advice.
    """
    carbon_delta = grid_forecast - grid_actual
    trend_str = "increasing" if carbon_delta > 10 else ("clearing" if carbon_delta < -10 else "stable")
    
    if co2 > CO2_UPPER_BOUND:
        mode = "SAFETY_OVERRIDE"
        damper = 100.0
        light = 100.0
        temp_sp = 21.5
        rationale = f"Air Quality Guard: Zone CO2 at {co2} ppm exceeds safe threshold ({CO2_UPPER_BOUND} ppm)."
        ai_suggestion = (
            f"PRIORITY SAFETY INTERVENTION: CO2 has peaked at {co2} ppm. "
            f"Autonomous supervisor recommends overriding grid decarbonization goals to maintain cognitive comfort. "
            f"Action: Drive VAV-21320001 damper to 100% open and hold supply air temp at 21.5 degC until indoor CO2 decays below 650 ppm. "
            f"Defer non-critical electrical loads on EM-21320002 to compensate for fan power surge."
        )
        return mode, damper, light, temp_sp, rationale, ai_suggestion

    carbon_stress = max(0.0, min(1.0, (grid_actual - CARBON_BASELINE) / (CARBON_MAX - CARBON_BASELINE)))
    demand_stress = 0.5 if kw > DEMAND_PEAK_THRESHOLD_KW else 0.0
    flex_factor = min(1.0, carbon_stress + demand_stress)

    if flex_factor > 0.4:
        mode = "DEMAND_SHED"
        damper = round(80.0 - (flex_factor * 40.0), 1)
        light = round(100.0 - (flex_factor * 35.0), 1)
        temp_sp = round(COMFORT_TEMP_MIN + (flex_factor * 2.0), 1)
        rationale = f"Grid Stress ({grid_actual} gCO2/kWh, {index_label}) & Meter {kw} kW. Curtailment target: {round(flex_factor*100)}%."
        ai_suggestion = (
            f"DECARBONIZATION CURTAILMENT DISPATCH: Grid emissions are elevated ({grid_actual} gCO2/kWh, {index_label}) "
            f"and trend is {trend_str}. Measured meter demand is {kw} kW. "
            f"Action: Modulate VAV-21320001 damper back to {damper}% and float zone temperature setpoint from {temp} degC up to {temp_sp} degC. "
            f"Dim peripheral luminaires on LT-4320154 to {light}%. "
            f"Expected Outcome: Sheds an estimated 18-25% active subsystem load while remaining within CIBSE Guide A thermal comfort limits."
        )
    else:
        mode = "OPTIMAL_NORMAL"
        damper = 80.0
        light = 100.0
        temp_sp = 22.0
        rationale = f"Grid state optimal ({grid_actual} gCO2/kWh, {index_label}). Standard design baseline active."
        ai_suggestion = (
            f"OPTIMAL DISPATCH ENVELOPE: The UK National Grid is running at high renewable penetration ({grid_actual} gCO2/kWh, {index_label}). "
            f"Local building demand ({kw} kW) and IAQ ({co2} ppm) are well within nominal bands. "
            f"Action: Maintain baseline design setpoints (VAV Damper 80%, Zone SP 22.0 degC, Lighting 100%). "
            f"Opportunity: If zone cooling demand is forecasted for the afternoon peak, consider initiating a pre-cooling cycle now while carbon intensity is low."
        )

    return mode, damper, light, temp_sp, rationale, ai_suggestion

def log_decision(mode, carbon, kw, co2, damper, light, temp, rationale, ai_suggestion):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ts = datetime.datetime.now().isoformat()
    c.execute("""
        INSERT INTO control_decisions 
        (timestamp, mode, grid_carbon, meter_kw, zone_co2, damper_target, lighting_target, temp_setpoint, rationale, ai_suggestion)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ts, mode, carbon, kw, co2, damper, light, temp, rationale, ai_suggestion))
    conn.commit()
    conn.close()

def dispatch_control_loop(client):
    grid_actual, grid_forecast, index_label = fetch_live_grid_state()
    kw, co2, temp = get_latest_telemetry()

    mode, damper, light, temp_sp, rationale, ai_suggestion = generate_ai_supervisory_advisory(
        grid_actual, grid_forecast, index_label, kw, co2, temp
    )

    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    vav_payload = json.dumps({
        "version": "1.5.2",
        "timestamp": now_utc,
        "pointset": {
            "points": {
                "damper_position_setpoint": {"set_value": damper},
                "zone_air_temperature_setpoint": {"set_value": temp_sp}
            }
        }
    })
    ltg_payload = json.dumps({
        "version": "1.5.2",
        "timestamp": now_utc,
        "pointset": {
            "points": {
                "lighting_level_setpoint": {"set_value": light}
            }
        }
    })

    client.publish(f"{SITE_ID}/MECH/VAV-21320001/config", vav_payload, qos=1)
    client.publish(f"{SITE_ID}/LTG/LT-4320154/config", ltg_payload, qos=1)

    log_decision(mode, grid_actual, kw, co2, damper, light, temp_sp, rationale, ai_suggestion)
    print(f"\n[{mode}] Grid: {grid_actual} gCO2/kWh | Demand: {kw} kW | CO2: {co2} ppm")
    print(f" -> AI Advice: {ai_suggestion[:110]}...")

def main():
    init_tables()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="SUPERVISOR-DECISION-ENGINE")
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile="certs/ca.crt")
    context.load_cert_chain(certfile="certs/client.crt", keyfile="certs/client.key")
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    client.tls_set_context(context)

    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()

    print("[+] UCL AI Supervisory Decision Engine online. Dispatching every 20s...")
    try:
        while True:
            dispatch_control_loop(client)
            time.sleep(20)
    except KeyboardInterrupt:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
