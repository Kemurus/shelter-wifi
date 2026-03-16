from flask import Blueprint, render_template, request, session, redirect, url_for
from ..auth import check_credentials

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect('/')

    error = None
    username = ''

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if check_credentials(username, password):
            session.permanent = True
            session['logged_in'] = True
            session['username'] = username
            return redirect(request.args.get('next') or '/')
        error = 'Неверный логин или пароль'

    return render_template('login.html', error=error, username=username)


@bp.route('/logout')
def logout():
    session.clear()
    return redirect('/login')
