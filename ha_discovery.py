#!/usr/bin/env python3
"""
Home Assistant MQTT Auto-Discovery Generator for Breckner 8.2kW Inverter
------------------------------------------------------------------------
Publishes discovery configurations for all 15 inverter sensors to MQTT.
Home Assistant will automatically construct device and entity entities without
editing configuration.yaml.

Author: Parfion Vladut
License: MIT
"""

import subprocess
import json

MQTT_HOST = "127.0.0.1"
PREFIX = "homeassistant/sensor/breckner"
STATE_TOPIC = "homeassistant/sensor/breckner_inverter/state"

# Sensor metadata structure:
# key: [Friendly Name, Unit of Measurement, Device Class, State Class]
SENSORS = {
    "grid_voltage": ["Grid Voltage", "V", "voltage", "measurement"],
    "grid_frequency": ["Grid Frequency", "Hz", "frequency", "measurement"],
    "ac_output_voltage": ["AC Output Voltage", "V", "voltage", "measurement"],
    "ac_output_frequency": ["AC Output Frequency", "Hz", "frequency", "measurement"],
    "ac_output_apparent_power": ["Apparent Power", "VA", "apparent_power", "measurement"],
    "ac_output_active_power": ["Active Power", "W", "power", "measurement"],
    "load_percentage": ["Load Percentage", "%", "power_factor", "measurement"],
    "bus_voltage": ["BUS Voltage", "V", "voltage", "measurement"],
    "battery_voltage": ["Battery Voltage", "V", "voltage", "measurement"],
    "battery_charging_current": ["Battery Charging Current", "A", "current", "measurement"],
    "battery_capacity": ["Battery Capacity", "%", "battery", "measurement"],
    "inverter_temperature": ["Inverter Temperature", "°C", "temperature", "measurement"],
    "pv_input_voltage": ["PV Voltage", "V", "voltage", "measurement"],
    "pv_input_current": ["PV Current", "A", "current", "measurement"],
    "pv_input_watts": ["PV Power", "W", "power", "measurement"],
    "battery_discharge_current": ["Battery Discharge Current", "A", "current", "measurement"]
}


def publish_discovery():
    print("Publishing Home Assistant MQTT Discovery payloads...")

    for key, val in SENSORS.items():
        config_topic = f"{PREFIX}_{key}/config"
        
        payload = {
            "name": f"Breckner {val[0]}",
            "unique_id": f"breckner_inverter_{key}",
            "state_topic": STATE_TOPIC,
            "value_template": f"{{{{ value_json.{key} }}}}",
            "unit_of_measurement": val[1],
            "device_class": val[2],
            "state_class": val[3],
            "device": {
                "identifiers": ["breckner_82kw_inverter"],
                "name": "Breckner 8.2kW Hybrid Inverter",
                "model": "Voltronic Axpert 8.2kW Clone",
                "manufacturer": "Breckner Germany"
            }
        }

        # Publish retained discovery message
        result = subprocess.run(
            ["mosquitto_pub", "-h", MQTT_HOST, "-t", config_topic, "-m", json.dumps(payload), "-r"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"  ✓ Registered entity: Breckner {val[0]}")
        else:
            print(f"  ✗ Failed to register: Breckner {val[0]} ({result.stderr.strip()})")

    print("\nMQTT Discovery completed successfully!")


if __name__ == "__main__":
    publish_discovery()