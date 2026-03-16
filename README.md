# Shelter WiFi Router

Open-source WiFi repeater for bomb shelters, built on **Raspberry Pi Zero 2W** + **Alfa AWUS036NH** USB adapter.

Designed for emergency use in conflict zones — provides an open hotspot for shelter occupants with client isolation and a web management UI.

![Status UI](https://raw.githubusercontent.com/Kemurus/shelter-wifi/main/docs/screenshot.png)

---

## How It Works

```
Shelter clients → uap0 (hotspot) → Pi Zero 2W → wlan1 (Alfa) → upstream WiFi → Internet
                                              → wlan0 (built-in) → management WiFi (SSH/Web UI)
```

| Interface | Role | Description |
|-----------|------|-------------|
| `wlan0` | Management | Built-in WiFi — connects to your management network for SSH/Web UI access |
| `uap0` | Hotspot AP | Virtual AP on wlan0 hardware — broadcasts the shelter hotspot |
| `wlan1` | Upstream | Alfa USB adapter — connects to internet source |

---

## Hardware Requirements

- **Raspberry Pi Zero 2W** (BCM43436 chip — supports concurrent AP+STA)
- **Alfa AWUS036NH** USB WiFi adapter (or any RT2800-based adapter)
- **USB OTG cable** (micro-USB to USB-A) for the Alfa adapter
- **MicroSD card** (8GB+)
- **Power bank or 5V power supply**

---

## Features

- Open hotspot for shelter clients (no password required)
- **Client isolation** — shelter clients cannot see each other (L2 + L3)
- **Web UI** on port 8080 — scan networks, configure hotspot, view connected clients, kick clients
- **Auto-watchdog** — monitors AP health, fixes routing and DNS automatically
- **Session-based auth** with 5-minute timeout
- Web UI accessible only from management network (not from shelter clients)

---

## Installation

### 1. Flash Raspberry Pi OS Lite (64-bit)

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/). During flashing:
- Set hostname (e.g. `shelter-pi`)
- Enable SSH
- **Do NOT configure WiFi** in the imager — we'll do it via install script

### 2. Clone the repository onto the Pi

```bash
sudo git clone https://github.com/Kemurus/shelter-wifi.git /opt/shelter-wifi
cd /opt/shelter-wifi
```

### 3. Create your config file

```bash
cp config/config.env.template config/config.env
nano config/config.env
```

Fill in your values:

```bash
MGMT_SSID="YourManagementWiFi"        # WiFi for SSH/admin access (wlan0)
MGMT_PASSWORD="your_password"

UPSTREAM_SSID="YourInternetWiFi"      # WiFi for internet (Alfa / wlan1)
UPSTREAM_PASSWORD="your_password"

HOTSPOT_SSID="Shelter_Hotspot"        # Name of the shelter hotspot
HOTSPOT_PASSWORD=""                   # Leave empty for open network

ADMIN_USER="admin"                    # Web UI username
ADMIN_PASSWORD="change_me_strong!"    # Web UI password (use strong password!)

COUNTRY="IL"                          # Your country code (IL, US, DE, etc.)
```

### 4. Run the installer

```bash
sudo bash scripts/install.sh
```

The Pi will reboot automatically. After reboot:
- Hotspot `HOTSPOT_SSID` will be broadcasting
- Web UI available at `http://<Pi-IP>:8080` from your management network
- SSH available at `ssh <user>@<Pi-IP>`

---

## Web UI

| Tab | Description |
|-----|-------------|
| **Status** | Connection map — shows upstream WiFi, management WiFi, hotspot SSID, connected clients, signal, temperature |
| **Networks** | Scan and connect Alfa (wlan1) to a different upstream WiFi network |
| **Hotspot** | Change SSID, channel, set/remove password |
| **Clients** | View connected devices, kick clients by MAC |

---

## Configuration Files

| File | Description |
|------|-------------|
| `config/config.env` | **Your secrets** — never commit this file |
| `config/config.env.template` | Template — safe to commit |
| `config/hostapd.conf` | AP settings (auto-managed by web UI) |
| `config/dnsmasq.conf` | DHCP/DNS for hotspot clients |

---

## Systemd Services

| Service | Description |
|---------|-------------|
| `shelter-interfaces` | Creates `uap0` virtual AP interface |
| `shelter-iptables` | NAT rules + client isolation |
| `shelter-routing` | Sets wlan1 as primary default route |
| `shelter-watchdog` | Auto-fixes AP, routing, and DNS every 10s |
| `shelter-wifi` | Flask web app via Gunicorn (port 8080) |

---

## Troubleshooting

**Hotspot not visible after reboot:**
```bash
sudo systemctl status hostapd
sudo journalctl -u hostapd -n 30
```

**No internet for clients:**
```bash
ip route show default          # wlan1 should have metric 50
sudo iptables -t nat -L -n -v  # check MASQUERADE rule on wlan1
```

**Web UI not accessible:**
```bash
sudo systemctl status shelter-wifi
sudo journalctl -u shelter-wifi -n 20
```

**Force restart everything:**
```bash
sudo systemctl restart shelter-interfaces shelter-iptables shelter-routing hostapd shelter-watchdog shelter-wifi
```

---

## Security Notes

- Web UI is blocked from hotspot clients (iptables INPUT rules)
- Shelter clients are isolated from each other (`ap_isolate=1` + iptables DROP)
- Shelter clients cannot reach your management network (192.168.50.0/24 blocked)
- Use a strong `ADMIN_PASSWORD` — the web UI controls your network

---

## License

MIT — free to use, modify, and distribute. If this helps someone stay connected during an emergency, that's the point.
