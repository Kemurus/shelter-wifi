import threading
import time

from flask import Blueprint, jsonify, request
from ..services import wpa

bp = Blueprint('networks', __name__, url_prefix='/api/networks')

# Scan state shared across requests
_scan_cache = {'results': [], 'scanning': False, 'last_scan': 0}
_scan_lock = threading.Lock()

# Connect job state
_connect_job = {'running': False, 'success': None, 'error': None, 'ssid': ''}
_connect_lock = threading.Lock()


def _background_scan():
    with _scan_lock:
        _scan_cache['scanning'] = True
    try:
        wpa.scan()
        time.sleep(3)
        results = wpa.get_scan_results()
        with _scan_lock:
            _scan_cache['results'] = results
            _scan_cache['last_scan'] = time.time()
    except Exception:
        pass
    finally:
        with _scan_lock:
            _scan_cache['scanning'] = False


def _background_connect(ssid, password):
    with _connect_lock:
        _connect_job['running'] = True
        _connect_job['success'] = None
        _connect_job['error'] = None
        _connect_job['ssid'] = ssid
    try:
        success = wpa.connect(ssid, password)
        with _connect_lock:
            _connect_job['success'] = success
    except Exception as e:
        with _connect_lock:
            _connect_job['error'] = str(e)
    finally:
        with _connect_lock:
            _connect_job['running'] = False


@bp.route('/scan', methods=['POST'])
def trigger_scan():
    if not _scan_cache['scanning']:
        t = threading.Thread(target=_background_scan, daemon=True)
        t.start()
    return jsonify({'status': 'scanning'})


@bp.route('/scan/results', methods=['GET'])
def scan_results():
    return jsonify({
        'scanning': _scan_cache['scanning'],
        'last_scan': _scan_cache['last_scan'],
        'networks': _scan_cache['results'],
    })


@bp.route('/connect', methods=['POST'])
def connect():
    data = request.get_json(silent=True) or {}
    ssid = data.get('ssid', '').strip()
    password = data.get('password', '').strip()
    if not ssid:
        return jsonify({'error': 'ssid required'}), 400
    if _connect_job['running']:
        return jsonify({'error': 'connection already in progress'}), 409

    t = threading.Thread(target=_background_connect, args=(ssid, password), daemon=True)
    t.start()
    return jsonify({'status': 'connecting', 'ssid': ssid}), 202


@bp.route('/connect/status', methods=['GET'])
def connect_status():
    with _connect_lock:
        return jsonify({
            'running': _connect_job['running'],
            'success': _connect_job['success'],
            'error': _connect_job['error'],
            'ssid': _connect_job['ssid'],
        })


@bp.route('/disconnect', methods=['POST'])
def disconnect():
    try:
        wpa.disconnect()
        return jsonify({'status': 'disconnected'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
