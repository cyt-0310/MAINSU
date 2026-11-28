"""Account verification and workspace ownership for the local web app."""
from contextlib import closing
from contextvars import ContextVar
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from uuid import uuid4
from urllib.parse import urlsplit

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.routing import Route
import web_postgres as pg


ARCHIVE = Path(__file__).resolve().parents[3] / 'MAINSU-upload' / 'github-share'
DATA = Path(os.environ.get('MAINSU_WEB_DATA', ARCHIVE / 'web_data')).resolve()
COOKIE = 'mainsu_session'
SESSION_SECONDS = 30 * 24 * 60 * 60
workspace = ContextVar('mainsu_workspace')


def database():
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATA / 'accounts.sqlite3')
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
            salt BLOB NOT NULL, password_hash BLOB NOT NULL, targets TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL, expires INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS legacy_owner (
            slot INTEGER PRIMARY KEY CHECK (slot = 1), account_id TEXT NOT NULL
        );
    """)
    return closing(conn)


def response(data, status=200):
    return JSONResponse(data, status_code=status, headers={'Cache-Control': 'no-store'})


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600_000)


def public_account(conn, account):
    legacy = conn.execute('SELECT 1 FROM legacy_owner WHERE account_id = ?', (account['id'],)).fetchone()
    return {'id': account['id'], 'email': account['email'], 'name': account['name'],
            'targets': json.loads(account['targets']) if account['targets'] is not None else None,
            'legacy': bool(legacy), 'pointBalance': None}


def postgres_account(conn, account):
    return {'id': account['id'].hex, 'email': account['email'], 'name': account['display_name'],
            'targets': pg.targets(conn, account['id']), 'legacy': False, 'pointBalance': account['point_balance']}


def packed_password(salt, secret_hash):
    return f'pbkdf2_sha256$600000${salt.hex()}${secret_hash.hex()}'


def matches_postgres_password(password, packed):
    try:
        scheme, rounds, salt, expected = (packed or '').split('$')
        if (scheme, rounds) == ('pbkdf2_sha256', '600000'):
            return hmac.compare_digest(password_hash(password, bytes.fromhex(salt)), bytes.fromhex(expected))
    except ValueError:
        pass
    password_hash(password, bytes(16))
    return False


def auth(token):
    if not token or len(token) != 43:
        return None
    if pg.enabled():
        with pg.connect() as conn:
            account = conn.execute(
                'SELECT u.* FROM public.users u JOIN public.web_login_sessions s ON s.user_id=u.id '
                'WHERE s.token_hash=%s AND s.expires > %s', (digest(token), int(time.time())),
            ).fetchone()
            return postgres_account(conn, account) if account else None
    with database() as conn:
        account = conn.execute(
            'SELECT a.* FROM accounts a JOIN sessions s ON s.account_id = a.id '
            'WHERE s.token_hash = ? AND s.expires > ?', (digest(token), int(time.time())),
        ).fetchone()
        return public_account(conn, account) if account else None


def authenticate(action, body, old_token):
    email = str(body.get('email', '')).strip().lower()
    password = body.get('password')
    if not isinstance(password, str) or len(password) > 128:
        raise ValueError('請輸入有效的密碼。')
    name = str(body.get('name', '')).strip()
    if action == 'register':
        if len(email) > 254 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
            raise ValueError('請輸入有效的電子郵件格式。')
        if not 1 <= len(name) <= 100 or len(password) < 8:
            raise ValueError('請填寫姓名或暱稱，密碼需至少 8 個字元。')
    if pg.enabled():
        return authenticate_postgres(action, email, name, password, old_token)
    with database() as conn, conn:
        if action == 'register':
            account_id, salt = uuid4().hex, secrets.token_bytes(16)
            conn.execute('INSERT INTO accounts VALUES (?, ?, ?, ?, ?, NULL)',
                         (account_id, email, name, salt, password_hash(password, salt)))
        else:
            account = conn.execute('SELECT * FROM accounts WHERE email = ?', (email,)).fetchone()
            actual = password_hash(password, account['salt'] if account else bytes(16))
            if not account or not hmac.compare_digest(actual, account['password_hash']):
                raise ValueError('電子郵件或密碼不正確，請確認是否已完成註冊。')
            account_id = account['id']
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        conn.execute('DELETE FROM sessions WHERE expires <= ? OR token_hash = ?', (now, digest(old_token)))
        conn.execute('INSERT INTO sessions VALUES (?, ?, ?)', (digest(token), account_id, now + SESSION_SECONDS))
        row = conn.execute('SELECT * FROM accounts WHERE id = ?', (account_id,)).fetchone()
        return public_account(conn, row), token


def authenticate_postgres(action, email, name, password, old_token):
    with pg.connect() as conn:
        if action == 'register':
            salt = secrets.token_bytes(16)
            account = conn.execute(
                'INSERT INTO public.users (email, display_name, password_hash) VALUES (%s,%s,%s) '
                'ON CONFLICT DO NOTHING RETURNING *',
                (email, name, packed_password(salt, password_hash(password, salt))),
            ).fetchone()
            if account is None:
                raise sqlite3.IntegrityError('duplicate email')
        else:
            account = conn.execute('SELECT * FROM public.users WHERE lower(email)=%s', (email,)).fetchone()
            if not matches_postgres_password(password, account['password_hash'] if account else None):
                raise ValueError('電子郵件或密碼不正確。')
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        conn.execute('DELETE FROM public.web_login_sessions WHERE expires <= %s OR token_hash=%s',
                     (now, digest(old_token)))
        conn.execute('INSERT INTO public.web_login_sessions (token_hash,user_id,expires) VALUES (%s,%s,%s)',
                     (digest(token), account['id'], now + SESSION_SECONDS))
        return postgres_account(conn, account), token


def checked_targets(entries):
    from web_portfolios import clean_target, school_id

    if not isinstance(entries, list) or len(entries) > 6:
        raise ValueError('最多可儲存 6 組申請校系。')
    targets = [{'school': clean_target(item.get('school')), 'department': clean_target(item.get('department'))}
               for item in entries if isinstance(item, dict)]
    if len({school_id(**target) for target in targets}) != len(entries):
        raise ValueError('校系資料重複或格式不正確。')
    return targets


def update_account(account_id, body):
    name = str(body['name']).strip() if 'name' in body else None
    if name is not None and not 1 <= len(name) <= 100:
        raise ValueError('姓名或暱稱需為 1 到 100 個字元。')
    targets = checked_targets(body['targets']) if 'targets' in body else None
    if pg.enabled():
        with pg.connect() as conn:
            row = conn.execute('SELECT * FROM public.users WHERE id=%s FOR UPDATE', (account_id,)).fetchone()
            if name is not None:
                row = conn.execute('UPDATE public.users SET display_name=%s WHERE id=%s RETURNING *',
                                   (name, account_id)).fetchone()
            if targets is not None:
                pg.save_targets(conn, account_id, targets)
            return postgres_account(conn, row)
    with database() as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        if name is not None:
            conn.execute('UPDATE accounts SET name = ? WHERE id = ?', (name, account_id))
        if targets is not None:
            from web_portfolios import school_id
            ids = {school_id(**target) for target in targets}
            previous = conn.execute('SELECT targets FROM accounts WHERE id = ?', (account_id,)).fetchone()['targets']
            if previous and {school_id(**target) for target in json.loads(previous)} - ids:
                raise ValueError('校系已更新，請重新整理後再儲存。')
            conn.execute('UPDATE accounts SET targets = ? WHERE id = ?', (json.dumps(targets, ensure_ascii=False), account_id))
        return public_account(conn, conn.execute('SELECT * FROM accounts WHERE id = ?', (account_id,)).fetchone())


def logout(token):
    if token and pg.enabled():
        with pg.connect() as conn:
            conn.execute('DELETE FROM public.web_login_sessions WHERE token_hash=%s', (digest(token),))
    elif token:
        with database() as conn, conn:
            conn.execute('DELETE FROM sessions WHERE token_hash = ?', (digest(token),))


async def account_endpoint(request):
    action = request.path_params['action']
    token = request.cookies.get(COOKIE, '')
    try:
        if action == 'logout' and request.method == 'POST':
            await run_in_threadpool(logout, token)
            reply = response({'ok': True})
            reply.delete_cookie(COOKIE, httponly=True, samesite='strict')
            return reply
        if action in ('register', 'login') and request.method == 'POST':
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError('帳號資料格式不正確。')
            account, new_token = await run_in_threadpool(authenticate, action, body, token)
            reply = response(account, 201 if action == 'register' else 200)
            reply.set_cookie(COOKIE, new_token, max_age=SESSION_SECONDS, httponly=True,
                             samesite='strict', secure=request.url.scheme == 'https')
            return reply
        account = await run_in_threadpool(auth, token)
        if not account:
            return response({'error': '請先登入。'}, 401)
        expected = request.headers.get('x-mainsu-account')
        if expected and expected != account['id']:
            return response({'error': '登入帳號已變更，請重新整理。'}, 409)
        if action == 'me' and request.method == 'GET':
            return response(account)
        if action == 'me' and request.method == 'PATCH':
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError('帳號資料格式不正確。')
            return response(await run_in_threadpool(update_account, account['id'], body))
        return response({'error': '找不到此操作。'}, 404)
    except (ValueError, TypeError) as error:
        # Login has the same response for missing accounts and wrong passwords.
        if action == 'login':
            return response({'error': '電子郵件或密碼不正確，請確認是否已完成註冊。'}, 401)
        return response({'error': str(error) if type(error) is ValueError else '資料格式不正確。'}, 400)
    except sqlite3.IntegrityError:
        return response({'error': '這個電子郵件已註冊，請直接登入。'}, 409)


async def protect_workspaces(request, call_next):
    path = request.url.path
    if not path.startswith('/api/') or path == '/api/health':
        return await call_next(request)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        if origin and urlsplit(origin).netloc.lower() != request.headers.get('host', '').lower():
            return response({'error': '請從 MAINSU 網頁操作。'}, 403)
    if path.startswith('/api/account/'):
        return await call_next(request)
    account = await run_in_threadpool(auth, request.cookies.get(COOKIE, ''))
    if not account:
        return response({'error': '請先登入。'}, 401)
    expected = request.headers.get('x-mainsu-account')
    if expected and expected != account['id']:
        return response({'error': '登入帳號已變更，請重新整理。'}, 409)
    private_root = DATA / ('postgres_cache' if pg.enabled() else 'workspaces') / account['id']
    request.state.workspace = private_root
    marker = workspace.set(DATA if account['legacy'] else private_root)
    postgres_marker = pg.owner.set(account['id'] if pg.enabled() else None)
    try:
        if pg.enabled() and path.startswith(('/api/portfolios', '/api/voice-interviews')):
            needs_portfolios = path.startswith('/api/portfolios') or (
                request.method == 'POST' and not path.endswith('/free-report')
            )
            if needs_portfolios:
                await run_in_threadpool(pg.hydrate_portfolios, account['id'], private_root)
        return await call_next(request)
    finally:
        pg.owner.reset(postgres_marker)
        workspace.reset(marker)


routes = [Route('/api/account/{action}', account_endpoint, methods=['GET', 'POST', 'PATCH'])]
