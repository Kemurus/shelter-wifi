from datetime import timedelta
from flask import Flask, redirect, session, request
from .routes import status, networks, hotspot, clients
from .routes.auth_routes import bp as auth_bp


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'sh3lt3r-w1f1-s3cr3t-k3y-ch4ng3-m3'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=5)
    app.config['WPA_IFACE']   = 'wlan1'
    app.config['AP_IFACE']    = 'uap0'
    app.config['MGMT_IFACE']  = 'wlan0'
    app.config['HOSTAPD_CONF'] = '/opt/shelter-wifi/config/hostapd.conf'
    app.config['WPA_CONF']    = '/etc/wpa_supplicant/wpa_supplicant-wlan1.conf'

    app.register_blueprint(auth_bp)
    app.register_blueprint(status.bp)
    app.register_blueprint(networks.bp)
    app.register_blueprint(hotspot.bp)
    app.register_blueprint(clients.bp)

    @app.route('/')
    def index():
        if not session.get('logged_in'):
            return redirect('/login')
        from flask import render_template
        return render_template('index.html')

    # Protect all /api/* routes
    @app.before_request
    def require_login():
        if request.path.startswith('/api/') and not session.get('logged_in'):
            return ('Unauthorized', 401)

    return app
