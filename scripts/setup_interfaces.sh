#!/bin/bash
# Create virtual AP interface uap0 on built-in wlan0 hardware.
# wlan0 stays as STA (connected to management WiFi — configured via NetworkManager).
# uap0 is the hotspot for shelter clients.
set -e

# Create virtual AP interface if it doesn't exist
if ! ip link show uap0 &>/dev/null; then
    iw dev wlan0 interface add uap0 type __ap
    echo "Created uap0 virtual AP interface"
fi

# Set static IP on uap0
ip link set uap0 up
ip addr flush dev uap0 2>/dev/null || true
ip addr add 192.168.4.1/24 dev uap0

# Ensure wlan1 is up (wpa_supplicant manages it)
ip link set wlan1 up 2>/dev/null || true

echo "Interfaces ready: uap0=192.168.4.1/24, wlan0=STA(management), wlan1=STA(upstream)"
