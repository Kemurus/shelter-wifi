"""
wpa_cli wrapper for managing wlan1 (upstream WiFi connection).
All operations use subprocess calls to wpa_cli to avoid extra dependencies.
"""
import subprocess
import time
from typing import Dict, List, Optional

_IFACE = 'wlan1'


def _run(*args, timeout: int = 10) -> str:
    """Run wpa_cli command, return stdout. Raises RuntimeError on failure."""
    cmd = ['wpa_cli', '-i', _IFACE] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'wpa_cli command timed out: {args}')
    except FileNotFoundError:
        raise RuntimeError('wpa_cli not found — is wpasupplicant installed?')


def scan() -> None:
    """Trigger a WiFi scan on wlan1. Non-blocking."""
    out = _run('scan')
    if 'OK' not in out and 'FAIL' in out:
        raise RuntimeError(f'wpa_cli scan failed: {out}')


def get_scan_results() -> List[Dict]:
    """Return list of visible networks after a scan."""
    out = _run('scan_results')
    networks = []
    for line in out.splitlines()[1:]:  # skip header line
        parts = line.split('\t')
        if len(parts) >= 5:
            networks.append({
                'bssid': parts[0],
                'frequency': int(parts[1]) if parts[1].isdigit() else 0,
                'signal': int(parts[2]) if parts[2].lstrip('-').isdigit() else 0,
                'flags': parts[3],
                'ssid': parts[4],
            })
    # Sort by signal strength descending
    networks.sort(key=lambda n: n['signal'], reverse=True)
    return networks


def get_status() -> Dict:
    """Return dict of current wpa_supplicant status for wlan1."""
    out = _run('status')
    status = {}
    for line in out.splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            status[k.strip()] = v.strip()
    return status


def connect(ssid: str, password: str) -> bool:
    """
    Connect to an upstream WiFi network.
    Blocks up to 20 seconds waiting for COMPLETED state.
    Returns True on success.
    """
    # Remove all existing networks first
    disconnect()

    # Add new network
    net_id = _run('add_network').strip()
    if not net_id.isdigit():
        raise RuntimeError(f'add_network failed: {net_id}')

    _run('set_network', net_id, 'ssid', f'"{ssid}"')

    if password:
        _run('set_network', net_id, 'psk', f'"{password}"')
    else:
        _run('set_network', net_id, 'key_mgmt', 'NONE')

    _run('enable_network', net_id)
    _run('save_config')

    # Wait up to 20s for association
    for _ in range(20):
        time.sleep(1)
        st = get_status()
        if st.get('wpa_state') == 'COMPLETED':
            return True

    return False


def disconnect() -> None:
    """Remove all configured networks and disconnect."""
    out = _run('list_networks')
    for line in out.splitlines()[1:]:
        parts = line.split('\t')
        if parts and parts[0].isdigit():
            _run('remove_network', parts[0])
    _run('save_config')


def get_signal_dbm() -> Optional[int]:
    """Return current signal level in dBm, or None if not connected."""
    out = _run('signal_poll')
    for line in out.splitlines():
        if line.startswith('RSSI='):
            try:
                return int(line.split('=', 1)[1])
            except ValueError:
                pass
    return None
