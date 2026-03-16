# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Flask web application running on a **Raspberry Pi Zero 2W** that acts as a WiFi router/hotspot manager for shelter networking. The app manages a 3-interface setup and provides a web UI (Russian language) for configuration.

## Running the Application

```bash
# Production (via systemd)
sudo systemctl start shelter-wifi

# Manual (Gunicorn)
gunicorn --workers 1 --bind 0.0.0.0:8080 --timeout 60 wsgi:app

# Debug (Flask dev server, port 80)
python wsgi.py
```

## Installation

```bash
sudo bash scripts/install.sh
```

No test suite or linter is configured in this project.

## Network Architecture

The Raspberry Pi has 3 network interfaces:

| Interface | Role | Description |
|-----------|------|-------------|
| `wlan0` | Management | Built-in WiFi; STA mode connecting to management network; also hosts `uap0` virtual AP |
| `uap0` | Hotspot AP | Virtual AP on wlan0; broadcasts the shelter hotspot (192.168.4.0/24) |
| `wlan1` | Upstream | Alfa USB WiFi adapter; STA mode connecting to internet source |

Traffic flow: Hotspot clients → uap0 → NAT (iptables) → wlan1 → internet

## Application Architecture

**Flask app** (`app/__init__.py`) registers 5 blueprints:
- `auth` — `/login`, `/logout`
- `status` — `/api/status` (upstream WiFi, hotspot, system stats)
- `networks` — `/api/networks/*` (scan, connect, disconnect upstream wlan1)
- `hotspot` — `/api/hotspot/config` (SSID, channel, password via hostapd.conf)
- `clients` — `/api/clients/` (DHCP lease list, deauth by MAC)

All `/api/*` routes require session authentication. Login reads credentials from `/opt/shelter-wifi/config/admin.conf` (default: `admin` / `shelter`).

**Service layer** (`app/services/`) wraps subprocess calls to system tools:
- `wpa.py` — calls `wpa_cli` to manage wlan1 (scan, connect, disconnect)
- `network_status.py` — reads `/proc/uptime`, `/sys/class/thermal/`, dnsmasq leases
- `config_writer.py` — atomic read/write of `hostapd.conf`
- `hostapd_mgr.py` — reloads hostapd via `hostapd_cli` or `systemctl restart`

**Systemd service chain** (order matters):
1. `shelter-interfaces.service` — creates uap0, sets static IPs
2. `shelter-iptables.service` — NAT rules
3. `shelter-routing.service` — default route via wlan1
4. `shelter-watchdog.service` — monitors wlan0 channel, syncs AP config
5. `shelter-wifi.service` — runs Flask via Gunicorn

## Key Configuration Files

- `/opt/shelter-wifi/config/hostapd.conf` — AP config (SSID, channel, WPA2 password). Written atomically by `config_writer.py`.
- `/opt/shelter-wifi/config/dnsmasq.conf` — DHCP range 192.168.4.10–100, DNS 8.8.8.8/8.8.4.4
- `/opt/shelter-wifi/config/admin.conf` — admin credentials (plain text key=value)
- `app/__init__.py` — interface names (`WPA_IFACE=wlan1`, `AP_IFACE=uap0`, `MGMT_IFACE=wlan0`) are defined here

## Important Notes

- The `SECRET_KEY` is hardcoded in `app/__init__.py` — do not commit changes that expose it further.
- `networks.py` uses Python `threading` for async WiFi scan/connect operations (wpa_supplicant calls can block).
- Client L2 isolation is enforced via `ap_isolate=1` in hostapd; L3 isolation is enforced via iptables DROP rules.
- The frontend (`templates/index.html`, `static/js/app.js`) polls `/api/status` for live updates.
