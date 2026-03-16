from flask import Blueprint, jsonify
from ..services import wpa, network_status

bp = Blueprint('status', __name__, url_prefix='/api')


def _wlan0_status():
    """Get wlan0 (built-in, management) connection info via wpa_cli."""
    try:
        import subprocess
        out = subprocess.run(
            ['wpa_cli', '-i', 'wlan0', 'status'],
            capture_output=True, text=True, timeout=5
        ).stdout
        info = {}
        for line in out.splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                info[k.strip()] = v.strip()
        connected = info.get('wpa_state') == 'COMPLETED'
        return {
            'connected': connected,
            'ssid': info.get('ssid', ''),
            'ip_address': info.get('ip_address', ''),
        }
    except Exception:
        return {'connected': False, 'ssid': '', 'ip_address': ''}


@bp.route('/status', methods=['GET'])
def status():
    wpa_st = wpa.get_status()
    connected = wpa_st.get('wpa_state') == 'COMPLETED'
    return jsonify({
        'upstream': {
            'connected': connected,
            'ssid': wpa_st.get('ssid', ''),
            'bssid': wpa_st.get('bssid', ''),
            'ip_address': wpa_st.get('ip_address', ''),
            'signal_dbm': wpa.get_signal_dbm() if connected else None,
        },
        'management': _wlan0_status(),
        'hotspot': {
            'ssid': network_status.get_hotspot_ssid(),
            'clients': network_status.get_client_count(),
        },
        'system': {
            'uptime': network_status.get_uptime(),
            'cpu_temp': network_status.get_cpu_temp(),
        }
    })
