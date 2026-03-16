#!/bin/bash
# NAT: wlan1 (upstream/guest) → uap0 (shelter hotspot)
# wlan0 stays untouched (management SSH)
set -e

WAN=wlan1   # Alfa — upstream guest WiFi
LAN=uap0    # virtual AP — shelter clients

iptables -F
iptables -t nat -F
iptables -t mangle -F
iptables -X

iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Loopback
iptables -A INPUT -i lo -j ACCEPT

# Established/related
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow everything on wlan0 (management interface — SSH, etc.)
iptables -A INPUT -i wlan0 -j ACCEPT

# Allow web UI on port 8080 from shelter clients (uap0)
iptables -A INPUT -i "$LAN" -p tcp --dport 8080 -j ACCEPT
iptables -A INPUT -i "$LAN" -p udp --dport 53 -j ACCEPT
iptables -A INPUT -i "$LAN" -p udp --dport 67 -j ACCEPT
iptables -A INPUT -i "$LAN" -p icmp -j ACCEPT

# FORWARD
iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A FORWARD -i "$LAN" -o "$WAN" -j ACCEPT
# Block client-to-client at L3 (belt-and-suspenders with ap_isolate=1)
iptables -A FORWARD -i "$LAN" -o "$LAN" -j DROP

# NAT
iptables -t nat -A POSTROUTING -o "$WAN" -j MASQUERADE

sysctl -w net.ipv4.ip_forward=1

iptables-save > /opt/shelter-wifi/config/iptables.rules
echo "iptables rules applied."
