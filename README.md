# **Breckner 8.2kW (Voltronic/Axpert Clone) Native Python MQTT Poller for Home Assistant**

A lightweight, robust Python polling script designed to integrate Breckner Germany 8.2kW Hybrid Inverters (and similar Voltronic/Axpert clones) directly with Home Assistant via local MQTT.

This project was built to replace failing Docker-based C binary pollers (inverter_poller), which crash or misalign on 8.2kW models due to serial buffer overflows and non-standard leading response bytes.

🌟 Why This Exists

Standard off-the-shelf C binaries (like inverter_poller) often fail on newer 8.2kW Voltronic clones because:

1. Buffer Pollution: Overlapping queries cause response packets (QPIGS) to linger in the Linux TTY buffer, causing command response misalignments.

2. Byte Offset Shifts: Fixed byte-offset parsing crashes when leading null/junk bytes are returned.

3. Container Limitations: Restricted shell environments inside minimal Docker containers lack standard binary utilities like xxd or hexdump.

Key Features
*  ⚡ **Native Python Direct Serial Access:** Uses low-level OS file descriptors for non-blocking raw serial reading without heavy dependencies.

*  🧹 **Automatic Buffer Flushing:** Clears stale serial data before every command to eliminate framing errors.

*  🔍 **Dynamic Token Alignment:** Locates the framing start character ( dynamically instead of relying on fixed string indices.

*  🤖 **Home Assistant Auto-Discovery:** Automatically registers 15+ sensors into Home Assistant via MQTT Discovery, no Manual YAML editing required.

📊 Monitored Telemetry
The script parses the full 17-parameter QPIGS payload and exposes:

|Category |	Sensor Name |	Unit |
| --- | --- | --- |
|Grid	Grid | Voltage, Grid Frequency |	V, Hz |
|AC Output |	AC Voltage, AC Frequency, Apparent Power, Active Power, Load % |	V, Hz, VA, W, % |
|Solar (PV) |	PV Voltage, PV Current, PV Power |	V, A, W |
|Battery |	Voltage, Capacity, Charging Current, Discharge Current |	V, %, A, A |
|Diagnostics |	Internal BUS Voltage, Heatsink Temperature |	V, °C |

📦 Prerequisites
*  Hardware: Breckner Germany 8.2kW Hybrid Inverter (or Voltronic Axpert 8.2kW clone) connected to host via RS232-to-USB cable (typically /dev/ttyUSB0).

* Software:
   - Python 3.x
   - Local MQTT Broker (e.g., Mosquitto MQTT Add-on in Home Assistant)
   - mosquitto-clients installed on the host system

🚀 Step-by-Step Tutorial
Step 1: Download & Configure Script
1. Clone or download this repository to your host machine:

```
git clone https://github.com/parfionvladut/breckner-8.2kw-inverter-mqtt.git
cd breckner-8.2kw-inverter-mqtt
```

2. Open inverter_mqtt.py and set your serial port and MQTT host IP address:

```
PORT = "/dev/ttyUSB0"      # Your inverter serial port
MQTT_HOST = "127.0.0.1"    # Local Home Assistant MQTT Broker IP
```

Step 2: Register MQTT Discovery Sensors in Home Assistant
Run the discovery auto-configuration script once to create the entities inside Home Assistant automatically:

```
python3 ha_discovery.py
```

All 15 sensors will immediately appear under Settings $\rightarrow$ Devices & Services $\rightarrow$ MQTT $\rightarrow$ Breckner 8.2kW Hybrid Inverter.

Step 3: Run the Poller Script
Method A: Direct Background Execution (nohup)
For quick execution on Home Assistant OS or Linux terminal:

```
nohup python3 inverter_mqtt.py > /dev/null 2>&1 &
```

Verify the process is active:

```
ps aux | grep inverter_mqtt.py
```

Method B: Local Docker Container (Recommended for Boot Persistence)
To run the poller as an isolated background container that starts automatically on boot:

1. Build the local image:

```
docker build -t local-inverter-poller .
```
2. Run the container with serial hardware passthrough:

```
docker run -d \
  --name inverter_poller \
  --restart always \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  --network host \
  local-inverter-poller
```
3. Check live logs:

```
docker logs -f inverter_poller
```

🛠️ Verification & Troubleshooting
Check if live data is publishing correctly to your MQTT broker by running:

```
mosquitto_sub -h 127.0.0.1 -t "homeassistant/sensor/breckner_inverter/state" -v
```

Expected JSON Stream:

 
> {"grid_voltage": 230.1, "grid_frequency": 49.9, "ac_output_voltage": 230.0, "ac_output_frequency": 50.0, "ac_output_apparent_power": 2002, "ac_output_active_power": 1793, "load_percentage": 24, "bus_voltage": 409.0, "battery_voltage": 52.0, "battery_charging_current": 0, "battery_capacity": 38, "inverter_temperature": 35, "pv_input_current": 0.0, "pv_input_voltage": 0.0, "pv_input_watts": 0.0, "battery_discharge_current": 39}

If you receive Malformed response, verify that no other legacy containers (such as inverter_poller) are actively locking /dev/ttyUSB0.
