import sqlite3
import datetime
import requests
from flask import Flask, render_template_string

DB_PATH = "telemetry_store.db"
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>UCL BSEER | AI Supervisory Demand Response Testbed</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {
      --ucl-dark-blue: #002855;
      --ucl-light-blue: #007FAC;
      --ucl-gold: #CC8A00;
      --ucl-green: #609F36;
      --ucl-pink: #D41B53;
      --ucl-charcoal: #262626;
      --ucl-mid-grey: #8C8279;
      --ucl-light-grey: #F4F4F6;
      --ucl-card-bg: #FFFFFF;
      --ucl-border: #E2E2E6;
    }
    * { box-sizing: border-box; }
    body { font-family: "Helvetica Neue", Arial, sans-serif; margin: 0; background: var(--ucl-light-grey); color: var(--ucl-charcoal); }
    header { background: var(--ucl-dark-blue); color: #fff; padding: 16px 32px; display: flex; justify-content: space-between; align-items: center; border-bottom: 4px solid var(--ucl-light-blue); }
    .brand-mark { font-size: 28px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; border-right: 2px solid rgba(255,255,255,0.3); padding-right: 18px; margin-right: 18px; }
    .header-titles h1 { font-size: 18px; margin: 0; font-weight: 600; }
    .header-titles p { margin: 2px 0 0 0; font-size: 12px; color: #CBD5E1; }
    .container { max-width: 1400px; margin: 0 auto; padding: 24px; }

    /* AI Supervisory Advisor Card */
    .ai-box {
      background: #FFFFFF;
      border: 1px solid #CBD5E1;
      border-left: 6px solid var(--ucl-light-blue);
      border-radius: 6px;
      padding: 20px 24px;
      margin-bottom: 24px;
      box-shadow: 0 2px 6px rgba(0, 40, 85, 0.06);
    }
    .ai-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }
    .ai-title {
      font-size: 13px;
      font-weight: 800;
      color: var(--ucl-dark-blue);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .ai-body {
      font-size: 14.5px;
      line-height: 1.6;
      color: #1E293B;
      font-weight: 500;
      background: #F8FAFC;
      padding: 14px 18px;
      border-radius: 4px;
      border: 1px solid #E2E8F0;
    }

    .status-badge {
      font-size: 11px;
      font-weight: 700;
      padding: 5px 12px;
      border-radius: 4px;
      letter-spacing: 0.04em;
    }
    .mode-OPTIMAL_NORMAL { background: #E8F5E9; color: var(--ucl-green); border: 1px solid #C8E6C9; }
    .mode-DEMAND_SHED { background: #FFF9C4; color: #F57F17; border: 1px solid #FFF59D; }
    .mode-SAFETY_OVERRIDE { background: #FCE4EC; color: var(--ucl-pink); border: 1px solid #F8BBD0; }
    .mode-STANDBY { background: #ECEFF1; color: #455A64; border: 1px solid #CFD8DC; }

    .kpi-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 24px; }
    .kpi-card { background: var(--ucl-card-bg); padding: 18px; border-radius: 6px; border: 1px solid var(--ucl-border); box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
    .kpi-card .label { font-size: 11px; font-weight: 700; color: var(--ucl-mid-grey); text-transform: uppercase; letter-spacing: 0.05em; }
    .kpi-card .val { font-size: 24px; font-weight: 700; color: var(--ucl-dark-blue); margin-top: 4px; }
    .kpi-card .sub { font-size: 11.5px; margin-top: 4px; }

    .grid-2 { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 24px; }
    .card { background: var(--ucl-card-bg); border-radius: 6px; border: 1px solid var(--ucl-border); padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); margin-bottom: 24px; }
    .card h3 { margin: 0 0 12px 0; font-size: 15px; color: var(--ucl-dark-blue); border-bottom: 2px solid var(--ucl-light-grey); padding-bottom: 8px; }

    table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }
    th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--ucl-border); }
    th { background: #FAFAFA; color: var(--ucl-dark-blue); font-weight: 600; }
    tr:hover { background: #F8FAFC; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; }
    .badge-elec { background: #FFF9C4; color: #F57F17; }
    .badge-mech { background: #EDE7F6; color: #512DA8; }
    .badge-iot  { background: #E8F5E9; color: var(--ucl-green); }
    .badge-ltg  { background: #E0F2FE; color: var(--ucl-light-blue); }
  </style>
</head>
<body>
  <header>
    <div style="display: flex; align-items: center;">
      <span class="brand-mark">UCL</span>
      <div class="header-titles">
        <h1>Bartlett School of Environment, Energy and Resources</h1>
        <p>AI Supervisory Control & Demand Response Testbed (UDMI v1.5.2 Ingestion)</p>
      </div>
    </div>
    <div style="text-align: right; font-size: 12px; color: #E2E8F0;">
      <span><strong>AI Dispatch Loop:</strong> Active (20s)</span><br>
      <span id="liveClock"></span>
    </div>
  </header>

  <div class="container">
    
    <!-- AI Decision Recommendation Banner -->
    <div class="ai-box">
      <div class="ai-header">
        <div class="ai-title">
          <span>?? AI Supervisory Control Advisory & Recommendation</span>
        </div>
        <span class="status-badge mode-{{ decision.mode }}">{{ decision.mode }}</span>
      </div>
      <div class="ai-body">
        {{ decision.ai_suggestion }}
      </div>
    </div>

    <!-- Live Metrics Grid -->
    <div class="kpi-grid">
      <div class="kpi-card" style="border-top: 4px solid var(--ucl-pink);">
        <div class="label">Grid Carbon</div>
        <div class="val">{{ decision.grid_carbon }} <span style="font-size: 14px;">gCO2</span></div>
        <div class="sub" style="color: var(--ucl-pink);">National Grid ESO API</div>
      </div>
      <div class="kpi-card" style="border-top: 4px solid #F57F17;">
        <div class="label">Active Demand</div>
        <div class="val">{{ stats.latest_kw }} <span style="font-size: 14px;">kW</span></div>
        <div class="sub" style="color: #F57F17;">Sub-meter EM-21320002</div>
      </div>
      <div class="kpi-card" style="border-top: 4px solid #512DA8;">
        <div class="label">VAV Damper SP</div>
        <div class="val">{{ decision.damper_target }}%</div>
        <div class="sub" style="color: #512DA8;">Target -> VAV-21320001</div>
      </div>
      <div class="kpi-card" style="border-top: 4px solid var(--ucl-light-blue);">
        <div class="label">Luminaire SP</div>
        <div class="val">{{ decision.lighting_target }}%</div>
        <div class="sub" style="color: var(--ucl-light-blue);">Target -> LT-4320154</div>
      </div>
      <div class="kpi-card" style="border-top: 4px solid var(--ucl-green);">
        <div class="label">Temp Setpoint</div>
        <div class="val">{{ decision.temp_setpoint }} degC</div>
        <div class="sub" style="color: var(--ucl-green);">Comfort Envelope Bound</div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h3>Live Subsystem Telemetry Dynamics</h3>
        <canvas id="telemetryChart" height="120"></canvas>
      </div>
      <div class="card">
        <h3>Recent AI Supervisory Decisions</h3>
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Mode</th>
              <th>Damper</th>
              <th>Light</th>
            </tr>
          </thead>
          <tbody>
            {% for d in decisions_log %}
            <tr>
              <td>{{ d[1].split("T")[-1][:8] if "T" in d[1] else d[1][-8:] }}</td>
              <td><strong>{{ d[2] }}</strong></td>
              <td>{{ d[6] }}%</td>
              <td>{{ d[7] }}%</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h3>Live Ingested Telemetry Ledger</h3>
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Subsystem</th>
            <th>Device Identifier</th>
            <th>Point Name</th>
            <th>Present Value</th>
            <th>Units</th>
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
          <tr>
            <td>{{ row[7] }}</td>
            <td>
              {% if row[2] == 'ELEC' %}
                <span class="badge badge-elec">ELEC</span>
              {% elif row[2] == 'MECH' %}
                <span class="badge badge-mech">MECH</span>
              {% elif row[2] == 'IOT' %}
                <span class="badge badge-iot">IOT</span>
              {% else %}
                <span class="badge badge-ltg">{{ row[2] }}</span>
              {% endif %}
            </td>
            <td><strong>{{ row[3] }}</strong></td>
            <td><code>{{ row[4] }}</code></td>
            <td><strong>{{ row[5] }}</strong></td>
            <td>{{ row[6] or '-' }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  <script>
    setInterval(() => {
      const d = new Date();
      document.getElementById('liveClock').innerText = d.toLocaleTimeString() + ' | ' + d.toISOString().slice(0,10);
    }, 1000);

    const chartData = {{ chart_json | safe }};
    const ctx = document.getElementById('telemetryChart').getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: chartData.labels,
        datasets: [{
          label: 'Observation Value',
          data: chartData.values,
          borderColor: '#007FAC',
          backgroundColor: 'rgba(0, 127, 172, 0.08)',
          borderWidth: 2,
          pointBackgroundColor: '#002855',
          pointRadius: 3,
          tension: 0.2,
          fill: true
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: '#262626' } } },
        scales: {
          x: { grid: { color: '#E2E2E6' }, ticks: { color: '#8C8279' } },
          y: { grid: { color: '#E2E2E6' }, ticks: { color: '#8C8279' } }
        }
      }
    });

    setTimeout(() => { window.location.reload(); }, 6000);
  </script>
</body>
</html>
"""

def query_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT present_value FROM udmi_telemetry WHERE subsystem = 'ELEC' ORDER BY id DESC LIMIT 1")
    elec_row = c.fetchone()
    latest_kw = round(elec_row[0], 2) if elec_row else 0.0

    c.execute("SELECT * FROM udmi_telemetry ORDER BY id DESC LIMIT 20")
    rows = c.fetchall()

    c.execute("SELECT timestamp, present_value FROM udmi_telemetry ORDER BY id DESC LIMIT 30")
    chart_raw = c.fetchall()[::-1]

    # Query closed-loop control log
    c.execute("""
        CREATE TABLE IF NOT EXISTS control_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, mode TEXT, grid_carbon REAL, meter_kw REAL,
            zone_co2 REAL, damper_target REAL, lighting_target REAL,
            temp_setpoint REAL, rationale TEXT, ai_suggestion TEXT
        )
    """)
    c.execute("SELECT * FROM control_decisions ORDER BY id DESC LIMIT 10")
    decisions_log = c.fetchall()
    conn.close()

    labels = [r[0].split("T")[-1][:8] if "T" in r[0] else r[0][-8:] for r in chart_raw]
    values = [r[1] for r in chart_raw]

    latest_dec = decisions_log[0] if decisions_log else (
        0, datetime.datetime.now().isoformat(), "STANDBY", 140.0, latest_kw, 500.0, 80.0, 100.0, 22.0,
        "Awaiting supervisor loop...",
        "AI Advisor initializing: Polling National Grid ESO API and building sub-meters..."
    )

    dec_obj = {
        "mode": latest_dec[2],
        "grid_carbon": latest_dec[3],
        "meter_kw": latest_dec[4],
        "zone_co2": latest_dec[5],
        "damper_target": latest_dec[6],
        "lighting_target": latest_dec[7],
        "temp_setpoint": latest_dec[8],
        "rationale": latest_dec[9],
        "ai_suggestion": latest_dec[10] if len(latest_dec) > 10 and latest_dec[10] else "Evaluating real-time optimization surface..."
    }

    return {"latest_kw": latest_kw}, rows, {"labels": labels, "values": values}, dec_obj, decisions_log

@app.route("/")
def index():
    stats, rows, chart_json, decision, decisions_log = query_database()
    return render_template_string(
        HTML_TEMPLATE,
        stats=stats,
        rows=rows,
        chart_json=chart_json,
        decision=decision,
        decisions_log=decisions_log
    )

if __name__ == "__main__":
    print("\n[+] UCL BSEER AI Supervisory Dashboard: http://127.0.0.1:8080\n")
    app.run(host="0.0.0.0", port=8080, debug=False)
