import re
import subprocess

from flask import Blueprint, jsonify
from ..services import network_status
from ..services.config_writer import read_hostapd_conf


def _get_ap_iface():
    return read_hostapd_conf().get('interface', 'uap0')

bp = Blueprint('clients', __name__, url_prefix='/api/clients')


def _valid_mac(mac: str) -> bool:
    return bool(re.match(r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$', mac))


@bp.route('/', methods=['GET'])
def list_clients():
    return jsonify({'clients': network_status.get_dhcp_clients()})


@bp.route('/<mac>', methods=['DELETE'])
def kick_client(mac):
    if not _valid_mac(mac):
        return jsonify({'error': 'invalid MAC address'}), 400
    result = subprocess.run(
        ['hostapd_cli', '-i', _get_ap_iface(), 'deauthenticate', mac],
        capture_output=True, text=True, timeout=5
    )
    if 'OK' in result.stdout:
        return jsonify({'status': 'kicked', 'mac': mac})
    return jsonify({'error': result.stdout.strip() or 'deauthenticate failed'}), 500
