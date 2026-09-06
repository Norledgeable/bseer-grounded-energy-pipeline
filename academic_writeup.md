\# UCL BSEER Research Testbed: UDMI Ingestion \& Semantic Grounding



\## 1. Objective

Establish an end-to-end, reproducible data pipeline that ingests real-world building telemetry over MQTT/mTLS, stores time-series observations in an indexed database, and couples dynamic building demand with real-time national grid carbon intensity.



\## 2. Methodology \& Implementation

\- \*\*Ingress \& Transport Security\*\*: Telemetry streamed from an operational broker (`10.128.104.30:8883`) via MQTT v3.1.1/v5 over Mutual TLS (mTLS). Client identity was validated using an X.509 EC certificate chain anchored to the lab CA, routed over a Tailscale mesh network.

\- \*\*Data Modeling \& Serialization\*\*: Implemented Google UDMI (Universal Device Management Interface) v1.5.2 schema definitions. Payload extraction filtered pointset events (`<site>/<subsystem>/<device\_id>/events/pointset`) from lifecycle metadata.

\- \*\*Persistence Store\*\*: Local SQLite store (`telemetry\_store.db`) structured with compound indexes on `(device\_id, point\_name, timestamp)` to support time-series retrieval.

\- \*\*Grid Carbon Integration\*\*: Real-time emission factors ingested via the National Grid ESO Carbon Intensity API (`api.carbonintensity.org.uk`).



\## 3. Results

\- Validated zero-drop ingestion across 100+ concurrent lighting (`LTG`) and indoor air quality (`IOT`) nodes.

\- Verified persistent separation of high-frequency telemetry from device state and metadata topics.

\- Built programmatic foundation for neuro-symbolic reasoning and automated demand flexibility using Brick Schema.

