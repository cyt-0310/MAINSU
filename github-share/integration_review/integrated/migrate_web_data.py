"""Import existing local MAINSU data into the configured Neon database."""
from contextlib import closing
from datetime import datetime, timezone
import json
import sqlite3
import time
from uuid import UUID

from web_accounts import DATA, packed_password
from web_portfolios import school_id
import web_postgres as pg


def local_records(data):
    for path in sorted(data.glob('*.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        if record.get('snapshot', {}).get('runtime', {}).get('finished') and not record.get('completedAt'):
            record['estimatedCompletedAt'] = modified_at.isoformat()
        yield record, modified_at


def import_account(conn, account):
    local_id = UUID(account['id'])
    password = packed_password(account['salt'], account['password_hash'])
    conn.execute(
        'INSERT INTO public.users (id,email,display_name,password_hash) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING',
        (local_id, account['email'], account['name'], password),
    )
    user = conn.execute('SELECT id,password_hash FROM public.users WHERE lower(email)=%s FOR UPDATE',
                        (account['email'].lower(),)).fetchone()
    if user is None:
        raise ValueError('The local account identifier conflicts with the database.')
    if not user['password_hash']:
        conn.execute('UPDATE public.users SET password_hash=%s WHERE id=%s', (password, user['id']))

    existing = pg.targets(conn, user['id'])
    keys = {school_id(**target) for target in existing}
    imported = json.loads(account['targets'] or '[]')
    merged = existing + [target for target in imported if school_id(**target) not in keys]
    pg.save_targets(conn, user['id'], merged)
    return user['id'], user['id'] == local_id and user['password_hash'] in (None, password)


def migrate():
    path = DATA / 'accounts.sqlite3'
    if not path.is_file():
        print('No local workspace database to import.')
        return
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as source, pg.connect() as conn:
        source.row_factory = sqlite3.Row
        source.execute('BEGIN')
        legacy = source.execute('SELECT account_id FROM legacy_owner').fetchone()
        accounts = source.execute('SELECT * FROM accounts ORDER BY id').fetchall()
        files = interviews = 0
        for account in accounts:
            user_id, can_preserve_session = import_account(conn, account)
            private = DATA / 'workspaces' / account['id']
            workspace = DATA if legacy and legacy['account_id'] == account['id'] else private
            for manifest in sorted((workspace / 'portfolios').glob('*/submission.json')):
                directory = manifest.parent
                portfolio_files = pg.files_in(directory)
                pg.save_portfolio_files(conn, user_id, directory, portfolio_files, import_only=True)
                files += len(portfolio_files)
            for directory in (workspace / 'voice_sessions', private / 'free_reports'):
                for record, modified_at in local_records(directory):
                    pg.save_interview(conn, user_id, record, modified_at, import_only=True)
                    interviews += 1
            if can_preserve_session:
                for session in source.execute('SELECT * FROM sessions WHERE account_id=? AND expires>?',
                                              (account['id'], int(time.time()))):
                    conn.execute(
                        'INSERT INTO public.web_login_sessions VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',
                        (session['token_hash'], user_id, session['expires']),
                    )
    print(f'Imported or already present: {len(accounts)} accounts, {interviews} interviews, {files} portfolio files.')


if __name__ == '__main__':
    try:
        migrate()
    except Exception as error:
        raise SystemExit(f'MAINSU import stopped before commit ({type(error).__name__}).') from None
