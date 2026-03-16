"""
Read system status: DHCP clients, hotspot SSID, uptime, CPU temperature.
"""
from typing import Dict, List

LEASE_FILE = '/var/lib/misc/dnsmasq.leases'
HOSTAPD_CONF = '/opt/shelter-wifi/config/hostapd.conf'


def get_dhcp_clients() -> List[Dict]:
    """Read dnsmasq lease file to get connected clients."""
    clients = []
    try:
        with open(LEASE_FILE) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 4:
                    clients.append({
                        'expires': parts[0],
                        'mac': parts[1],
                        'ip': parts[2],
                        'hostname': parts[3] if parts[3] != '*' else '',
                    })
    except FileNotFoundError:
        pass
    return clients


def get_client_count() -> int:
    return len(get_dhcp_clients())


def get_hotspot_ssid() -> str:
    try:
        with open(HOSTAPD_CONF) as f:
            for line in f:
                line = line.strip()
                if line.startswith('ssid='):
                    return line.split('=', 1)[1].strip()
    except Exception:
        pass
    return ''


def get_uptime() -> str:
    try:
        with open('/proc/uptime') as f:
            secs = float(f.read().split()[0])
        h = int(secs) // 3600
        m = (int(secs) % 3600) // 60
        return f'{h}h {m}m'
    except Exception:
        return 'unknown'


def get_cpu_temp() -> float:
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return 0.0
