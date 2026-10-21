#!/usr/bin/env python3
import os
import time
import json
import subprocess
import termios
import glob

# Try using dynamic IDs first, fall back to paths if directory is empty
CANDIDATE_PORTS = ["/dev/ttyUSB1", "/dev/ttyUSB0", "/dev/ttyACM0"]
MQTT_HOST = "127.0.0.1"
MQTT_TOPIC = "homeassistant/sensor/breckner_inverter/state"
POLL_INTERVAL = 5


def configure_port_native(fd):
    """Configures the raw file descriptor to 2400 baud, 8N1, raw mode using pure Python."""
    attrs = termios.tcgetattr(fd)
    
    # Set Baud Rate to 2400 (Input and Output)
    attrs[4] = termios.B2400  # ospeed
    attrs[5] = termios.B2400  # ispeed
    
    # Input flags: Ignore break, no parity, no CR translation
    attrs[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP | termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IXON)
    
    # Output flags: Raw output
    attrs[1] &= ~termios.OPOST
    
    # Control flags: 8 bits, no parity, 1 stop bit, enable receiver, ignore modem control
    attrs[2] &= ~(termios.CSIZE | termios.PARENB | termios.CSTOPB | termios.CRTSCTS)
    attrs[2] |= (termios.CS8 | termios.CREAD | termios.CLOCAL)
    
    # Local flags: Raw input (no echo, no canonical processing, no signals)
    attrs[3] &= ~(termios.ECHO | termios.ECHOE | termios.ECHOK | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN)
    
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def test_port(port):
    """Checks if a serial port is responsive to QPIGS using pure Python native attributes."""
    if not os.path.exists(port):
        return False
    try:
        fd = os.open(port, os.O_RDWR | os.O_NONBLOCK)
        configure_port_native(fd)
        termios.tcflush(fd, termios.TCIFLUSH)
        os.write(fd, b"\x51\x50\x49\x47\x53\xb7\xa9\x0d")
        time.sleep(0.8)
        try:
            res = os.read(fd, 512)
            os.close(fd)
            return b"(" in res and len(res) > 30
        except Exception:
            os.close(fd)
            return False
    except Exception:
        return False


def get_scan_targets():
    """Combines persistent /dev/serial/by-id/ paths with raw fallbacks."""
    by_id_paths = glob.glob("/dev/serial/by-id/*")
    return by_id_paths + CANDIDATE_PORTS


def find_active_port():
    """Scans all dynamic and static candidate ports to find the active connection."""
    targets = get_scan_targets()
    for port in targets:
        if test_port(port):
            print(f"✓ Connected to inverter on {port}")
            return port
    return None


def send_cmd_with_retry(fd, cmd_bytes, max_retries=3):
    """Sends command with retries and buffer flushing for unstable serial links."""
    for attempt in range(max_retries):
        termios.tcflush(fd, termios.TCIFLUSH)
        os.write(fd, cmd_bytes)
        time.sleep(0.8)
        try:
            res = os.read(fd, 512)
            if b"(" in res and len(res) > 30:
                return res
        except Exception:
            pass
        time.sleep(0.2)
    return b""


def parse_qpigs(raw_bytes):
    if not raw_bytes:
        print(" [DIAGNOSTIC] Reason: Received 0 bytes (Timeout or disconnected port).")
        return None

    try:
        str_data = raw_bytes.decode('latin-1', errors='ignore')

        # Check 1: Opening parenthesis missing
        start = str_data.find('(')
        if start == -1:
            print(f" [DIAGNOSTIC] Reason: Missing '(' in response. Raw Hex: {raw_bytes.hex(' ')}")
            print(f" [DIAGNOSTIC] Raw ASCII: {repr(str_data)}")
            return None

        # Check 2: Payload split
        payload = str_data[start + 1:].strip()
        parts = payload.split()

        if len(parts) < 16:
            print(f" [DIAGNOSTIC] Reason: Truncated stream. Expected >=16 fields, got {len(parts)}.")
            print(f" [DIAGNOSTIC] Received Fields: {parts}")
            print(f" [DIAGNOSTIC] Raw Hex: {raw_bytes.hex(' ')}")
            return None

        # Check 3: Field parsing validation
        return {
            "grid_voltage": float(parts[0]),
            "grid_frequency": float(parts[1]),
            "ac_output_voltage": float(parts[2]),
            "ac_output_frequency": float(parts[3]),
            "ac_output_apparent_power": int(parts[4]),
            "ac_output_active_power": int(parts[5]),
            "load_percentage": int(parts[6]),
            "bus_voltage": float(parts[7]),
            "battery_voltage": float(parts[8]),
            "battery_charging_current": int(parts[9]),
            "battery_capacity": int(parts[10]),
            "inverter_temperature": int(parts[11]),
            "pv_input_current": float(parts[12]),
            "pv_input_voltage": float(parts[13]),
            "pv_input_watts": round(float(parts[12]) * float(parts[13]), 1),
            "battery_discharge_current": int(parts[15])
        }

    except ValueError as ve:
        print(f" [DIAGNOSTIC] Reason: Value conversion error ({ve}).")
        print(f" [DIAGNOSTIC] Broken parts array: {parts}")
        return None
    except Exception as e:
        print(f" [DIAGNOSTIC] Reason: Unexpected parsing error ({e}). Raw Hex: {raw_bytes.hex(' ')}")
        return None


def main():
    qpigs_cmd = b"\x51\x50\x49\x47\x53\xb7\xa9\x0d"
    
    while True:
        port = find_active_port()
        if not port:
            print("Searching for active inverter serial port...")
            time.sleep(POLL_INTERVAL)
            continue

        try:
            fd = os.open(port, os.O_RDWR | os.O_NONBLOCK)
            configure_port_native(fd)
            failed_attempts = 0

            while failed_attempts < 5:
                raw = send_cmd_with_retry(fd, qpigs_cmd)
                data = parse_qpigs(raw)

                if data:
                    failed_attempts = 0
                    payload = json.dumps(data)
                    print(f"Polled Data: {payload}")
                    subprocess.run(
                        ["mosquitto_pub", "-h", MQTT_HOST, "-t", MQTT_TOPIC, "-m", payload],
                        capture_output=True
                    )
                else:
                    failed_attempts += 1
                    print(f"Malformed or missing data on {port} (warning {failed_attempts}/5)...")

                time.sleep(POLL_INTERVAL)

            # If 5 consecutive polls fail, close file descriptor and re-scan ports
            os.close(fd)
            print(f"Lost communication on {port}. Re-scanning ports...")

        except Exception as e:
            print(f"Serial port error: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
