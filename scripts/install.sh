#!/bin/bash
# Shelter WiFi — Full installer
# Usage: sudo bash scripts/install.sh
# Reads config from /opt/shelter-wifi/config/config.env

set -e
INSTALL_DIR="/opt/shelter-wifi"

echo "=== Shelter WiFi Installer ==="

# ── 1. Load config ────────────────────────────────────────────────────────────
if [[ ! -f "$INSTALL_DIR/config/config.env" ]]; then
    echo "ERROR: $INSTALL_DIR/config/config.env not found!"
    echo "Copy config/config.env.template to config/config.env and fill in passwords."
    exit 1
fi
source "$INSTALL_DIR/config/config.env"

for var in MGMT_SSID MGMT_PASSWORD UPSTREAM_SSID UPSTREAM_PASSWORD HOTSPOT_SSID ADMIN_USER ADMIN_PASSWORD COUNTRY; do
    if [[ -z "${!var}" ]]; then
        echo "ERROR: $var is not set in config.env"
        exit 1
    fi
done

echo "[1/10] Config loaded — hotspot: $HOTSPOT_SSID, country: $COUNTRY"

# ── 2. Install packages ───────────────────────────────────────────────────────
echo "[2/10] Installing packages..."
apt-get update -qq
apt-get install -y -qq \
    hostapd dnsmasq python3 python3-pip python3-venv \
    wpasupplicant iw wireless-tools net-tools iptables \
    network-manager
systemctl unmask hostapd 2>/dev/null || true

# ── 3. Install Python app ─────────────────────────────────────────────────────
echo "[3/10] Setting up Python venv..."
cd "$INSTALL_DIR"
python3 -m venv venv
venv/bin/pip install -q -r requirements.txt

# ── 4. Create admin credentials ───────────────────────────────────────────────
echo "[4/10] Writing admin.conf..."
cat > "$INSTALL_DIR/config/admin.conf" << EOF
username=$ADMIN_USER
password=$ADMIN_PASSWORD
EOF
chmod 600 "$INSTALL_DIR/config/admin.conf"

# ── 5. Create hostapd.conf ────────────────────────────────────────────────────
echo "[5/10] Writing hostapd.conf..."
cat > "$INSTALL_DIR/config/hostapd.conf" << EOF
interface=uap0
driver=nl80211
ctrl_interface=/var/run/hostapd
ctrl_interface_group=netdev
ssid=$HOTSPOT_SSID
hw_mode=g
channel=13
ieee80211n=1
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
ap_isolate=1
country_code=$COUNTRY
EOF

if [[ -n "$HOTSPOT_PASSWORD" ]]; then
    cat >> "$INSTALL_DIR/config/hostapd.conf" << EOF
wpa=2
wpa_passphrase=$HOTSPOT_PASSWORD
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF
fi
ln -sf "$INSTALL_DIR/config/hostapd.conf" /etc/hostapd/hostapd.conf

# ── 6. wpa_supplicant for wlan1 (Alfa / upstream) ────────────────────────────
echo "[6/10] Writing wpa_supplicant-wlan1.conf..."
cat > /etc/wpa_supplicant/wpa_supplicant-wlan1.conf << EOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=$COUNTRY

network={
    ssid="$UPSTREAM_SSID"
    psk="$UPSTREAM_PASSWORD"
    key_mgmt=WPA-PSK
    priority=1
}
EOF
chmod 600 /etc/wpa_supplicant/wpa_supplicant-wlan1.conf

# ── 7. NetworkManager — manage wlan0, ignore wlan1/uap0 ──────────────────────
echo "[7/10] Configuring NetworkManager..."
mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/shelter.conf << EOF
[main]
dns=none

[keyfile]
unmanaged-devices=interface-name:wlan1;interface-name:uap0
EOF

# Static resolv.conf — prevent NM/networkd from overwriting
cat > /etc/resolv.conf << EOF
nameserver 192.168.50.1
nameserver 8.8.8.8
EOF
chattr +i /etc/resolv.conf 2>/dev/null || true

# Fix nsswitch so DNS resolution actually works
sed -i 's/mdns4_minimal \[NOTFOUND=return\] //' /etc/nsswitch.conf

# Connect wlan0 to management WiFi
nmcli connection delete "$MGMT_SSID" 2>/dev/null || true
nmcli connection add type wifi ifname wlan0 con-name "$MGMT_SSID" \
    ssid "$MGMT_SSID" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$MGMT_PASSWORD" \
    connection.autoconnect yes \
    ipv4.method auto 2>/dev/null || true

# ── 8. systemd-networkd for wlan1 ────────────────────────────────────────────
echo "[8/10] Configuring systemd-networkd for wlan1..."

cat > /etc/systemd/network/10-wlan0.network << EOF
[Match]
Name=wlan0

[Link]
Unmanaged=yes
EOF

cat > /etc/systemd/network/20-wlan1.network << EOF
[Match]
Name=wlan1

[Network]
DHCP=ipv4
IPForward=yes

[DHCPv4]
RouteMetric=50
EOF

systemctl enable systemd-networkd
systemctl enable wpa_supplicant@wlan1

# ── 9. Install systemd services ───────────────────────────────────────────────
echo "[9/10] Installing systemd services..."

for svc in shelter-interfaces shelter-iptables shelter-routing shelter-watchdog shelter-wifi; do
    cp "$INSTALL_DIR/systemd/$svc.service" /etc/systemd/system/
done

# hostapd prestart — waits for wlan0 channel, sets it in hostapd.conf
cat > /usr/local/bin/hostapd-prestart.sh << 'PRESTART'
#!/bin/bash
for i in $(seq 1 30); do
    FREQ=$(/sbin/iw dev wlan0 link 2>/dev/null | awk '/freq:/{print $2}')
    if [[ -n "$FREQ" && "$FREQ" -ge 2412 ]]; then
        CH=$(( (FREQ - 2407) / 5 ))
        sed -i "s/^channel=.*/channel=$CH/" /opt/shelter-wifi/config/hostapd.conf
        logger -t hostapd-prestart "wlan0 freq=${FREQ} -> channel=$CH"
        exit 0
    fi
    sleep 2
done
sed -i 's/^channel=.*/channel=13/' /opt/shelter-wifi/config/hostapd.conf
logger -t hostapd-prestart 'fallback channel=13'
PRESTART
chmod +x /usr/local/bin/hostapd-prestart.sh

# hostapd drop-in
mkdir -p /etc/systemd/system/hostapd.service.d
cat > /etc/systemd/system/hostapd.service.d/shelter.conf << EOF
[Unit]
After=shelter-interfaces.service
Requires=shelter-interfaces.service

[Service]
ExecStartPre=/bin/rm -f /var/run/hostapd/uap0
ExecStartPre=/usr/local/bin/hostapd-prestart.sh
EOF

# dnsmasq
cp "$INSTALL_DIR/config/dnsmasq.conf" /etc/dnsmasq.d/shelter.conf

# watchdog
cp "$INSTALL_DIR/scripts/hostapd_watchdog.sh" /usr/local/bin/
chmod +x /usr/local/bin/hostapd_watchdog.sh

systemctl daemon-reload
systemctl enable shelter-interfaces shelter-iptables shelter-routing shelter-watchdog shelter-wifi hostapd

# ── 10. Set ownership ────────────────────────────────────────────────────────
echo "[10/10] Setting permissions..."
chown -R root:netdev "$INSTALL_DIR/config"
chmod 750 "$INSTALL_DIR/config"
chmod 640 "$INSTALL_DIR/config"/*.conf 2>/dev/null || true
chmod 600 "$INSTALL_DIR/config/admin.conf"
chmod 600 /etc/wpa_supplicant/wpa_supplicant-wlan1.conf

echo ""
echo "=== Installation complete! ==="
echo "Rebooting in 5 seconds..."
sleep 5
reboot
