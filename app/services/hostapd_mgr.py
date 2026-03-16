"""
Reload or restart hostapd after config changes.
"""
import subprocess
from .config_writer import read_hostapd_conf


def _ap_iface():
    """Get AP interface from hostapd.conf (uap0 or wlan0)."""
    cfg = read_hostapd_conf()
    return cfg.get('interface', 'uap0')


def reload() -> None:
    """
    Reload hostapd config via hostapd_cli reload.
    Falls back to systemctl restart if that fails.
    """
    iface = _ap_iface()
    result = subprocess.run(
        ['hostapd_cli', '-i', iface, 'reload'],
        capture_output=True, text=True, timeout=5
    )
    if 'OK' not in result.stdout:
        subprocess.run(
            ['sudo', 'systemctl', 'restart', 'hostapd'],
            check=True, timeout=15
        )
