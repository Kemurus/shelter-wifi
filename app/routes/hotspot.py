from flask import Blueprint, jsonify, request
from ..services import config_writer, hostapd_mgr

bp = Blueprint('hotspot', __name__, url_prefix='/api/hotspot')


@bp.route('/config', methods=['GET'])
def get_config():
    cfg = config_writer.read_hostapd_conf()
    return jsonify({
        'ssid': cfg.get('ssid', ''),
        'channel': cfg.get('channel', '13'),
        'has_password': 'wpa_passphrase' in cfg,
    })


@bp.route('/config', methods=['PUT'])
def set_config():
    data = request.get_json(silent=True) or {}
    updates = {}
    removes = []

    if 'ssid' in data:
        ssid = data['ssid'].strip()
        if not (1 <= len(ssid) <= 32):
            return jsonify({'error': 'SSID must be 1-32 characters'}), 400
        updates['ssid'] = ssid

    if 'channel' in data:
        ch = int(data['channel'])
        if ch not in range(1, 14):
            return jsonify({'error': 'Channel must be 1-13'}), 400
        updates['channel'] = str(ch)

    if data.get('open'):
        # Remove WPA settings — open network
        removes = ['wpa', 'wpa_passphrase', 'wpa_key_mgmt', 'wpa_pairwise', 'rsn_pairwise']
    elif 'password' in data:
        pw = data['password'].strip()
        if len(pw) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        updates['wpa'] = '2'
        updates['wpa_passphrase'] = pw
        updates['wpa_key_mgmt'] = 'WPA-PSK'
        updates['wpa_pairwise'] = 'TKIP'
        updates['rsn_pairwise'] = 'CCMP'

    if not updates and not removes:
        return jsonify({'error': 'Nothing to update'}), 400

    try:
        config_writer.write_hostapd_conf(updates, removes=removes)
        hostapd_mgr.reload()
        return jsonify({'status': 'updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
