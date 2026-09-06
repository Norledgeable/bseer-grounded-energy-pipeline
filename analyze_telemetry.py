"""
PhD Experiment: Telemetry Analysis & Grid-Carbon Correlation
UCL BSEER Research Testbed
"""
import sqlite3
import pandas as pd
import requests

DB_PATH = "telemetry_store.db"

def fetch_live_uk_carbon() -> dict:
    url = "https://api.carbonintensity.org.uk/intensity"
    try:
        r = requests.get(url, timeout=5).json()
        data = r["data"][0]["intensity"]
        return {
            "actual": data["actual"],
            "forecast": data["forecast"],
            "index": data["index"]
        }
    except Exception:
        return {"actual": 140, "forecast": 140, "index": "moderate"}

def analyze_iaq_and_energy():
    conn = sqlite3.connect(DB_PATH)

    # 1. Summary of captured telemetry by subsystem
    query_summary = """
        SELECT subsystem, 
               COUNT(DISTINCT device_id) as device_count, 
               COUNT(*) as total_samples,
               MIN(timestamp) as earliest_sample,
               MAX(timestamp) as latest_sample
        FROM udmi_telemetry
        GROUP BY subsystem
    """
    try:
        df_summary = pd.read_sql_query(query_summary, conn)
    except Exception as e:
        print(f"Database read error: {e}")
        conn.close()
        return

    # 2. Extract IAQ readings
    df_iaq = pd.read_sql_query("""
        SELECT device_id, point_name, present_value, raw_units, timestamp
        FROM udmi_telemetry
        WHERE subsystem = 'IOT'
        ORDER BY timestamp DESC
        LIMIT 50
    """, conn)

    # 3. Extract Lighting power readings
    df_ltg = pd.read_sql_query("""
        SELECT device_id, point_name, present_value, raw_units, timestamp
        FROM udmi_telemetry
        WHERE subsystem = 'LTG'
        ORDER BY timestamp DESC
        LIMIT 50
    """, conn)

    conn.close()

    # Fetch live grid carbon factor
    grid_carbon = fetch_live_uk_carbon()
    carbon_val = grid_carbon["actual"] if grid_carbon["actual"] else grid_carbon["forecast"]

    print("\n" + "=" * 65)
    print("      RESEARCH TELEMETRY ANALYTICS & GRID STATUS")
    print("=" * 65)
    print(f"National Grid Carbon: {carbon_val} gCO2/kWh ({grid_carbon['index']})")
    
    print("\n--- Ingested Subsystem Summary ---")
    if not df_summary.empty:
        print(df_summary.to_string(index=False))
    else:
        print("No telemetry rows recorded yet.")

    print("\n--- Recent IAQ Telemetry ---")
    if not df_iaq.empty:
        print(df_iaq.head(10).to_string(index=False))
    else:
        print("No IOT telemetry recorded yet.")

    print("\n--- Recent Lighting Telemetry ---")
    if not df_ltg.empty:
        print(df_ltg.head(10).to_string(index=False))
    else:
        print("No LTG telemetry recorded yet.")

    print("=" * 65 + "\n")

if __name__ == "__main__":
    analyze_iaq_and_energy()