#!/usr/bin/env python3
"""
Breckner 8.2kW Hybrid Inverter (Voltronic/Axpert Clone) MQTT Poller
-------------------------------------------------------------------
This script uses direct, non-blocking low-level OS file descriptors to query
the inverter over serial (RS232-to-USB). It flushes the serial buffer prior to
every request to prevent framing/alignment corruption and dynamically parses
the 17-field QPIGS telemetry response.

Author: Parfion Vladut
License: MIT
"""

import os
import time
import json
import subprocess

# Configuration
PORT = "/dev/ttyUSB0"      # Serial port connected to inverter
MQTT_HOST = "127.0.0.1"    # Local Home Assistant MQTT Broker IP
MQTT_TOPIC = "homeassistant/sensor/breckner_inverter/state"
POLL_INTERVAL = 5          # Polling delay in seconds


def send_cmd(fd, cmd_bytes):
    """
    Flushes stale bytes from the serial buffer and sends a raw CRC command.
    """
    # Sleep briefly to ensure any in-flight bytes arrive, then flush
    time.sleep(0.1)
    try:
        os.read(fd, 1024)
    except Exception:
        pass

    # Send command bytes to inverter
    os.write(fd, cmd_bytes)
    time.sleep(0.5)

    # Read response
    try:
        return os.read(fd, 512)
    except Exception:
        return b""


def parse_qpigs(raw_bytes):
    """
    Parses raw QPIGS response bytes into structured dictionary metrics.
    Dynamic search for '(' handles buffer shifts and leading garbage bytes.
    """
    try:
        str_data = raw_bytes.decode('latin-1', errors='ignore')
        
        # Locate start frame delimiter
        start = str_data.find('(')
        if start == -1:
            return None

        # Split space-delimited parameters
        parts = str_data[start + 1:].strip().split()
        if len(parts) < 16:
            return None

        # Extract parameters into structured dictionary
        grid_volts = float(parts[0])
        grid_freq = float(parts[1])
        ac_volts = float(parts[2])
        ac_freq = float(parts[3])
        ac_va = int(parts[4])
        ac_watt = int(parts[5])
        load_pct = int(parts[6])
        bus_volts = float(parts[7])
        bat_volts = float(parts[8])
        bat_charge_curr = int(parts[9])
        bat_cap = int(parts[10])
        temp = int(parts[11])
        pv_curr = float(parts[12])
        pv_volts = float(parts[13])
        pv_watts = round(pv_curr * pv_volts, 1)
        bat_discharge_curr = int(parts[15])

        return {
            "grid_voltage": grid_volts,
            "grid_frequency": grid_freq,
            "ac_output_voltage": ac_volts,
            "ac_output_frequency": ac_freq,
            "ac_output_apparent_power": ac_va,
            "ac_output_active_power": ac_watt,
            "load_percentage": load_pct,
            "bus_voltage": bus_volts,
            "battery_voltage": bat_volts,
            "battery_charging_current": bat_charge_curr,
            "battery_capacity": bat_cap,
            "inverter_temperature": temp,
            "pv_input_current": pv_curr,
            "pv_input_voltage": pv_volts,
            "pv_input_watts": pv_watts,
            "battery_discharge_current": bat_discharge_curr
        }
    except Exception as e:
        print(f"Parsing error: {e}")
        return None


def main():
    # Configure serial port: 2400 baud, 8N1, raw mode
    os.system(f"stty -F {PORT} 2400 cs8 -cstopb -parenb raw -echo")
    fd = os.open(PORT, os.O_RDWR | os.O_NONBLOCK)

    print("Starting Breckner 8.2kW Inverter MQTT Poller loop...")

    # QPIGS command with CRC checksum and carriage return: \x51\x50\x49\x47\x53\xb7\xa9\x0d
    qpigs_cmd = b"\x51\x50\x49\x47\x53\xb7\xa9\x0d"

    try:
        while True:
            raw = send_cmd(fd, qpigs_cmd)
            data = parse_qpigs(raw)

            if data:
                payload = json.dumps(data)
                print(f"Polled Data: {payload}")

                # Publish payload to local MQTT broker
                subprocess.run(
                    ["mosquitto_pub", "-h", MQTT_HOST, "-t", MQTT_TOPIC, "-m", payload],
                    capture_output=True
                )
            else:
                print("Received incomplete or malformed telemetry stream, retrying...")

            time.sleep(POLL_INTERVAL)
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()