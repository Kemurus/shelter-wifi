#!/bin/bash
# Watchdog: monitors AP, channel sync, routing, and DNS.
# Runs every 10s, auto-fixes everything.

PATH=/usr/sbin:/usr/bin:/sbin:/bin
LOG="logger -t shelter-watchdog"

last_freq=""

restart_ap() {
    local freq=$1
    local ch=$(( (freq - 2407) / 5 ))
    [[ "$ch" -lt 1 || "$ch" -gt 13 ]] && return

    $LOG "Restarting AP on channel $ch (freq=${freq}MHz)"

    # Update hostapd.conf with correct channel
    sed -i "s/^channel=.*/channel=$ch/" /opt/shelter-wifi/config/hostapd.conf

    # Recreate uap0 if needed
    if ! ip link show uap0 &>/dev/null; then
        iw dev wlan0 interface add uap0 type __ap 2>/dev/null || true
        ip link set uap0 up 2>/dev/null || true
        ip addr add 192.168.4.1/24 dev uap0 2>/dev/null || true
    fi

    # Remove stale ctrl socket so hostapd can start cleanly
    rm -f /var/run/hostapd/uap0

    systemctl restart hostapd
    sleep 3

    # Restart dnsmasq too (it needs uap0 to be up)
    systemctl restart dnsmasq 2>/dev/null || true

    $LOG "AP restarted: $(hostapd_cli -i uap0 status 2>/dev/null | grep state)"
}

fix_routing() {
    # Ensure wlan1 default route has lowest metric
    local wlan1_metric=$(ip route show default dev wlan1 2>/dev/null | grep -oP 'metric \K\d+')
    local wlan1_gw=$(ip route show default dev wlan1 2>/dev/null | awk '{print $3; exit}')

    if [[ -n "$wlan1_gw" && "$wlan1_metric" != "50" ]]; then
        ip route del default via "$wlan1_gw" dev wlan1 2>/dev/null
        ip route add default via "$wlan1_gw" dev wlan1 metric 50 2>/dev/null
        $LOG "Fixed wlan1 route: gateway=$wlan1_gw metric=50"
    fi
}

fix_dns() {
    # Ensure resolv.conf has working DNS
    if ! grep -q 'nameserver' /etc/resolv.conf 2>/dev/null; then
        echo -e "nameserver 192.168.50.1\nnameserver 8.8.8.8" > /etc/resolv.conf
        $LOG "Fixed empty resolv.conf"
    fi
}

check_internet() {
    # Quick connectivity check — ping gateway
    local gw=$(ip route show default dev wlan1 2>/dev/null | awk '{print $3; exit}')
    if [[ -n "$gw" ]]; then
        if ! ping -c 1 -W 2 "$gw" &>/dev/null; then
            $LOG "Gateway $gw unreachable, restarting wlan1"
            systemctl restart wpa_supplicant@wlan1 2>/dev/null || true
            sleep 5
            systemctl restart systemd-networkd 2>/dev/null || true
            sleep 5
            fix_routing
        fi
    fi
}

$LOG "Watchdog started"

while true; do
    sleep 10

    # 1. Get current wlan0 frequency (use iw since NM manages wlan0)
    freq=$(iw dev wlan0 link 2>/dev/null | awk '/freq:/{print $2}')

    # 2. Check AP health
    carrier=$(cat /sys/class/net/uap0/carrier 2>/dev/null)
    hostapd_alive=$(systemctl is-active hostapd 2>/dev/null)

    if [[ -z "$freq" || "$freq" -lt 2400 ]]; then
        # wlan0 not connected yet — wait
        continue
    fi

    # 3. Restart AP if needed
    if [[ "$carrier" != "1" || "$hostapd_alive" != "active" ]]; then
        $LOG "AP down (carrier=$carrier, hostapd=$hostapd_alive) — restarting"
        restart_ap "$freq"
    elif [[ -n "$last_freq" && "$freq" != "$last_freq" ]]; then
        $LOG "wlan0 channel changed $last_freq→$freq — resyncing AP"
        restart_ap "$freq"
    fi

    last_freq="$freq"

    # 4. Fix routing every cycle (cheap operation)
    fix_routing

    # 5. Fix DNS
    fix_dns

    # 6. Check internet every 6th cycle (~60s)
    cycle=$(( ${cycle:-0} + 1 ))
    if (( cycle % 6 == 0 )); then
        check_internet
    fi
done
