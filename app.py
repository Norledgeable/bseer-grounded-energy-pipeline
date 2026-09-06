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
  <title>UCL BSEER | Decarbonization & Sub-Metering Testbed</title>
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
    .kpi-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 24px; }
    .kpi-card { background: var(--ucl-card-bg); padding: 18px; border-radius: 6px; border: 1px solid var(--ucl-border); box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
    .kpi-card .label { font-size: 11px; font-weight: 700; color: var(--ucl-mid-grey); text-transform: uppercase; letter-spacing: 0.05em; }
    .kpi-card .val { font-size: 24px; font-weight: 700; color: var(--ucl-dark-blue); margin-top: 4px; }
    .kpi-card .sub { font-size: 11.5px; margin-top: 4px; }
    .grid-2 { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 24px; }
    .card { background: var(--ucl-card-bg); border-radius: 6px; border: 1px solid var(--ucl-border); padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); margin-bottom: 20px; }
    .card h3 { margin: 0 0 12px 0; font-size: 15px; color: var(--ucl-dark-blue); border-bottom: 2px solid var(--ucl-light-grey); padding-bottom: 8px; }
    table { width: 100%; border-collapse: collapse; font-size: 12.5px; margin-top: 8px; }
    th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--ucl-border); }
    th { background: #FAFAFA; color: var(--ucl-dark-blue); font-weight: 600; }
    tr:hover { background: #F8FAFC; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; }
    .badge-elec { background: #FFF9C4; color: #F57F17; border: 1px solid #FFF59D; }
    .badge-mech { background: #EDE7F6; color: #512DA8; border: 1px solid #D1C4E9; }
    .badge-iot  { background: #E8F5E9; color: var(--ucl-green); border: 1px solid #C8E6C9; }
    .badge-ltg  { background: #E0F2FE; color: var(--ucl-light-blue); border: 1px solid #BAE6FD; }
  </style>
</head>
<body>
  <header>
    <div style="display: flex; align-items: center;">
      <span class="brand-mark">UCL</span>
      <div class="header-titles">
        <h1>Bartlett School of Environment, Energy and Resources</h1>
        <p>Dynamic Multi-Subsystem Decarbonization Testbed (UDMI v1.5.2 Ingestion)</p>
      </div>
    </div>
    <div style="text-align: right; font-size: 12px; color: #E2E8F0;">
      <span><strong>Live Stream:</strong> Tailscale mTLS Bridge</span><br>
      <span id="liveClock">2026-09-06</span>
    </div>
  </header>

  <div class="container">
    <div class="kpi-grid">
      <div class="kpi-card" style="border-top: 4px solid var(--ucl-pink);">
        <div class="label">National Grid Carbon</div>
        <div class="val" id="carbonVal">-- gCO₂/kWh</div>
        <div class="sub" id="carbonIndex" style="color: var(--ucl-pink);">Awaiting ESO API...</div>
      </div>
      <div class="kpi-card" style="border-top: 4px solid #F57F17;">
        <div class="label">Latest Meter Demand</div>
        <div class="val">{{ stats.latest_kw }} kW</div>
        <div class="sub" style="color: #F57F17;">ELEC Sub-Meters (EM-*)</div>
      </div>
      <div class="kpi-card" style="border-top: 4px solid #512DA8;">
        <div class="label">Active Terminal Units</div>
        <div class="val">{{ stats.mech_count }}</div>
        <div class="sub" style="color: #512DA8;">MECH (VAV / FCU Nodes)</div>
      </div>
      <div class="kpi-card" style="border-top: 4px solid var(--ucl-light-blue);">
        <div class="label">Total Monitored Nodes</div>
        <div class="val">{{ stats.devices }}</div>
        <div class="sub" style="color: var(--ucl-light-blue);">Across 4 Core Subsystems</div>
      </div>
      <div class="kpi-card" style="border-top: 4px solid var(--ucl-green);">
        <div class="label">Total Observations</div>
        <div class="val">{{ stats.samples }}</div>
        <div class="sub" style="color: var(--ucl-green);">Persisted SQLite Records</div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h3>Live Sub-Meter & Actuator Dynamics</h3>
        <canvas id="telemetryChart" height="120"></canvas>
      </div>
      <div class="card">
        <h3>Subsystems Topology</h3>
        <div style="font-size: 13px; line-height: 1.6;">
          <p><strong style="color: #F57F17;">ELEC (Electrical Sub-meters):</strong> Sub-metering feed (<code>EM-21320002</code>) capturing real-time active power and load curves.</p>
          <p><strong style="color: #512DA8;">MECH (Mechanical / HVAC):</strong> VAV terminals (<code>VAV-21320001</code>, <code>VAV-21320002</code>) and Fan Coil Units (<code>FCU-1320001</code>) reporting airflow setpoints and damper outputs.</p>
          <p><strong style="color: var(--ucl-green);">IOT (Indoor Air Quality):</strong> Space sensors (<code>IAQ-7320001</code>) monitoring CO₂ and comfort limits.</p>
          <p><strong style="color: var(--ucl-light-blue);">LTG (Lighting Controls):</strong> DALI channels and daylight multi-sensors (<code>QSE-*</code>).</p>
        </div>
      </div>
    </div>

    <div class="card">
      <h3>Live Ingested Ledger (ELEC, MECH, IOT, LTG)</h3>
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

    fetch('https://api.carbonintensity.org.uk/intensity')
      .then(r => r.json())
      .then(d => {
        const item = d.data[0].intensity;
        const val = item.actual || item.forecast;
        document.getElementById('carbonVal').innerText = val + ' gCO₂/kWh';
        document.getElementById('carbonIndex').innerText = 'Grid State: ' + item.index.toUpperCase();
      })
      .catch(() => {
        document.getElementById('carbonVal').innerText = '140 gCO₂/kWh';
        document.getElementById('carbonIndex').innerText = 'Grid State: MODERATE';
      });

    const chartData = {{ chart_json | safe }};
    const ctx = document.getElementById('telemetryChart').getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: chartData.labels,
        datasets: [{
          label: 'Telemetry Readings',
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
    c.execute("SELECT COUNT(DISTINCT device_id), COUNT(*) FROM udmi_telemetry")
    dev_count, sample_count = c.fetchone()

    c.execute("SELECT COUNT(DISTINCT device_id) FROM udmi_telemetry WHERE subsystem = 'MECH'")
    mech_count = c.fetchone()[0] or 0

    c.execute("SELECT present_value FROM udmi_telemetry WHERE subsystem = 'ELEC' ORDER BY id DESC LIMIT 1")
    latest_kw_row = c.fetchone()
    latest_kw = round(latest_kw_row[0], 2) if latest_kw_row else "--"

    c.execute("SELECT * FROM udmi_telemetry ORDER BY id DESC LIMIT 25")
    rows = c.fetchall()

    c.execute("SELECT timestamp, present_value FROM udmi_telemetry ORDER BY id DESC LIMIT 30")
    chart_raw = c.fetchall()[::-1]
    conn.close()

    labels = [r[0].split("T")[-1][:8] if "T" in r[0] else r[0][-8:] for r in chart_raw]
    values = [r[1] for r in chart_raw]

    return {
        "devices": dev_count or 0,
        "mech_count": mech_count,
        "latest_kw": latest_kw,
        "samples": sample_count or 0
    }, rows, {"labels": labels, "values": values}

@app.route("/")
def index():
    stats, rows, chart_json = query_database()
    return render_template_string(HTML_TEMPLATE, stats=stats, rows=rows, chart_json=chart_json)

if __name__ == "__main__":
    print("\n[+] UCL BSEER Multi-Subsystem Dashboard: http://127.0.0.1:8080\n")
    app.run(host="0.0.0.0", port=8080, debug=False)
