"""
Session-based authentication for the web UI.
"""
import functools
from flask import session, redirect, url_for, request

ADMIN_CONF = '/opt/shelter-wifi/config/admin.conf'
DEFAULT_USER = 'admin'
DEFAULT_PASS = 'shelter'


def read_credentials():
    user, passwd = DEFAULT_USER, DEFAULT_PASS
    try:
        with open(ADMIN_CONF) as f:
            for line in f:
                line = line.strip()
                if line.startswith('username='):
                    user = line.split('=', 1)[1]
                elif line.startswith('password='):
                    passwd = line.split('=', 1)[1]
    except FileNotFoundError:
        pass
    return user, passwd


def check_credentials(username, password):
    user, passwd = read_credentials()
    return username == user and password == passwd


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated
