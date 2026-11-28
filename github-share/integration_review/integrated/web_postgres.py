"""PostgreSQL storage for the MAINSU web app."""
from contextvars import ContextVar
import gzip
from datetime import datetime, timezone
from hashlib import md5
from pathlib import Path, PurePosixPath
import os
from tempfile import NamedTemporaryFile
from threading import Lock
from uuid import UUID


owner = ContextVar('mainsu_postgres_owner', default=None)
portfolio_lock = Lock()
portfolio_versions = {}


def enabled():
    return bool(os.environ.get('NEON_DATABASE_URL'))


def connect():
    from psycopg import connect as open_connection
    from psycopg.rows import dict_row

    return open_connection(os.environ['NEON_DATABASE_URL'], row_factory=dict_row, connect_timeout=10)


def jsonb(value):
    from psycopg.types.json import Jsonb

    return Jsonb(value)


def targets(conn, user_id):
    return conn.execute(
        'SELECT d.school_name AS school, d.department_name AS department '
        'FROM public.applications a JOIN public.departments d ON d.id = a.department_id '
        "WHERE a.user_id = %s AND (d.school_name,d.department_name) <> ('免費練習','通用面試') "
        'ORDER BY a.position NULLS LAST, a.created_at, a.id', (user_id,),
    ).fetchall()


def save_targets(conn, user_id, selections):
    from web_portfolios import school_id

    existing = {school_id(**item): item for item in targets(conn, user_id)}
    if existing.keys() - {school_id(**item) for item in selections}:
        raise ValueError('校系已更新，請重新整理後再儲存。')
    for position, target in enumerate(selections, 1):
        item = existing.get(school_id(**target), target)
        school, department = item['school'], item['department']
        conn.execute(
            'INSERT INTO public.departments (school_name, department_name) VALUES (%s, %s) '
            'ON CONFLICT (school_name, department_name) DO NOTHING', (school, department),
        )
        conn.execute(
            'INSERT INTO public.applications (user_id, department_id, position) '
            'SELECT %s, id, %s FROM public.departments WHERE school_name = %s AND department_name = %s '
            'ON CONFLICT (user_id, department_id) DO UPDATE SET position = EXCLUDED.position',
            (user_id, position, school, department),
        )


def interview_id(key):
    return UUID(str(key).removeprefix('free-'))


def portfolio_key(user_id, identity):
    return UUID(md5(f'{UUID(str(user_id))}:portfolio:{identity}'.encode()).hexdigest())


def ensure_portfolio(conn, user_id, target, identity):
    key = portfolio_key(user_id, identity)
    conn.execute(
        'INSERT INTO public.portfolios (id,user_id,name,parse_status,storage_key) '
        'VALUES (%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING',
        (key, user_id, f"{target['school']} {target['department']}", 'completed', identity),
    )
    return key


def save_interview(conn, user_id, record, updated_at=None, *, import_only=False):
    from postgres_interview_details import milliseconds, save_details

    session_id = interview_id(record['id'])
    snapshot = record.get('snapshot', {})
    runtime = snapshot.get('runtime', {})
    finished = bool(runtime.get('finished', record.get('finished')))
    existing = conn.execute(
        'SELECT user_id,application_id,portfolio_id,mode,web_record,ended_at FROM public.interview_sessions '
        'WHERE id=%s FOR UPDATE', (session_id,),
    ).fetchone()
    if existing and (existing['user_id'] != UUID(str(user_id))
                     or not existing['web_record'] or existing['web_record']['id'] != record['id']):
        raise ValueError('面試紀錄識別碼已被使用。')
    if import_only and existing:
        return
    if existing:
        application_id, portfolio_id, mode = (existing[key] for key in ('application_id', 'portfolio_id', 'mode'))
    else:
        target = record['target'] if snapshot else {'school': '免費練習', 'department': '通用面試'}
        conn.execute(
            'INSERT INTO public.departments (school_name,department_name) VALUES (%s,%s) '
            'ON CONFLICT (school_name,department_name) DO NOTHING',
            (target['school'], target['department']),
        )
        conn.execute(
            'INSERT INTO public.applications (user_id,department_id) SELECT %s,id FROM public.departments '
            'WHERE school_name=%s AND department_name=%s ON CONFLICT (user_id,department_id) DO NOTHING',
            (user_id, target['school'], target['department']),
        )
        application_id = conn.execute(
            'SELECT a.id FROM public.applications a JOIN public.departments d ON d.id=a.department_id '
            'WHERE a.user_id=%s AND d.school_name=%s AND d.department_name=%s',
            (user_id, target['school'], target['department']),
        ).fetchone()['id']
        mode = 'free' if not snapshot or record.get('noPortfolio') else 'personalized'
        portfolio_id = None
        if mode == 'personalized':
            identity = record.get('portfolioIdentity')
            if not identity:
                if import_only:
                    return save_legacy_interview(conn, user_id, record, updated_at, import_only=True)
                raise ValueError('無法辨識本場使用的備審版本。')
            portfolio_id = ensure_portfolio(conn, user_id, target, identity)
    modified = updated_at or datetime.now(timezone.utc)
    summary = snapshot.get('summary') or {}
    result = conn.execute(
        'INSERT INTO public.interview_sessions AS saved '
        '(id,user_id,application_id,portfolio_id,mode,started_at,ended_at,elapsed_ms,status,'
        'question_count,termination_reason,web_record) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) '
        'ON CONFLICT (id) DO UPDATE SET ended_at=EXCLUDED.ended_at,elapsed_ms=EXCLUDED.elapsed_ms,'
        'status=EXCLUDED.status,question_count=EXCLUDED.question_count,'
        'termination_reason=EXCLUDED.termination_reason,web_record=EXCLUDED.web_record '
        "WHERE saved.user_id=EXCLUDED.user_id AND saved.web_record->>'id'=EXCLUDED.web_record->>'id'",
        (session_id, user_id, application_id, portfolio_id, mode, record.get('createdAt'),
         (record.get('completedAt') or (existing and existing['ended_at']) or modified) if finished else None,
         milliseconds(snapshot.get('elapsed', sum(answer['duration'] for answer in record['answers']))),
         'completed' if finished else 'paused' if record.get('error') else 'active',
         snapshot.get('total_questions', len(record['answers'])), summary.get('termination_reason'),
         jsonb({**record, 'storageUpdatedAt': modified.isoformat()})),
    )
    if result.rowcount != 1:
        raise ValueError('面試紀錄識別碼已被使用。')
    save_details(conn, session_id, record, jsonb, portfolio_id)


def save_legacy_interview(conn, user_id, record, updated_at, *, import_only):
    finished = bool(record.get('snapshot', {}).get('runtime', {}).get('finished', record.get('finished')))
    statement = (
        'INSERT INTO public.web_interview_records AS saved (id, owner, finished, record, updated_at) '
        'VALUES (%s, %s, %s, %s, COALESCE(%s, clock_timestamp())) '
    )
    if import_only:
        statement += 'ON CONFLICT (id) DO NOTHING'
    else:
        statement += (
            'ON CONFLICT (id) DO UPDATE SET record=EXCLUDED.record, finished=EXCLUDED.finished, '
            "updated_at=EXCLUDED.updated_at WHERE saved.owner=EXCLUDED.owner AND saved.record->>'id'=EXCLUDED.record->>'id'"
        )
    result = conn.execute(statement, (interview_id(record['id']), user_id, finished, jsonb(record), updated_at))
    if not import_only and result.rowcount != 1:
        raise ValueError('面試紀錄識別碼已被使用。')


def load_interview(user_id, key):
    with connect() as conn:
        row = conn.execute(INTERVIEW_ROWS + ' WHERE id=%s', (user_id, user_id, interview_id(key))).fetchone()
    if row is None or row['record']['id'] != key:
        raise FileNotFoundError(key)
    return row


INTERVIEW_ROWS = (
    "WITH records AS (SELECT id, jsonb_set(web_record::jsonb,'{answers}',COALESCE(("
    "SELECT jsonb_agg(item || CASE WHEN a.id IS NULL THEN '{}'::jsonb ELSE "
    "jsonb_build_object('question',q.question_text,'text',a.transcript) END ORDER BY n) "
    "FROM jsonb_array_elements(web_record::jsonb->'answers') WITH ORDINALITY AS entries(item,n) "
    "LEFT JOIN public.answers a ON a.id=md5(s.id::text || ':answer:' || n)::uuid "
    "LEFT JOIN public.interview_questions q ON q.id=a.question_id),'[]'::jsonb)) AS record, "
    "status='completed' AS finished, "
    "COALESCE((web_record->>'storageUpdatedAt')::timestamptz,ended_at,started_at, "
    "'epoch'::timestamptz) AS updated_at FROM public.interview_sessions s "
    "WHERE user_id=%s AND web_record IS NOT NULL UNION ALL "
    "SELECT old.id,old.record,old.finished,old.updated_at FROM public.web_interview_records old "
    "WHERE old.owner=%s AND NOT EXISTS (SELECT 1 FROM public.interview_sessions s "
    "WHERE s.id=old.id AND s.user_id=old.owner AND s.web_record IS NOT NULL)) "
    "SELECT id, record, finished, updated_at FROM records"
)


def interviews(user_id, finished=None):
    query = INTERVIEW_ROWS
    params = (user_id, user_id)
    if finished is not None:
        query += ' WHERE finished=%s'
        params += (finished,)
    with connect() as conn:
        return conn.execute(query + ' ORDER BY updated_at DESC, id', params).fetchall()


def save_portfolio_files(conn, user_id, directory, files, *, import_only=False, school_key=None, create=False):
    key = f'{UUID(str(user_id))}:{school_key or directory.name}'
    if create:
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (key,))
        if conn.execute('SELECT 1 FROM public.web_portfolio_files WHERE portfolio_key=%s AND path=%s',
                        (key, 'submission.json')).fetchone():
            raise FileExistsError(key)
    statement = (
        'INSERT INTO public.web_portfolio_files AS saved (portfolio_key, owner, path, data, gzipped, size) '
        'VALUES (%s, %s, %s, %s, %s, %s) '
    )
    if import_only:
        statement += 'ON CONFLICT (portfolio_key, path) DO NOTHING'
    else:
        statement += (
            'ON CONFLICT (portfolio_key, path) DO UPDATE SET data=EXCLUDED.data, '
            'gzipped=EXCLUDED.gzipped, size=EXCLUDED.size, updated_at=clock_timestamp() '
            'WHERE saved.owner=EXCLUDED.owner'
        )
    for file in files:
        data = file.read_bytes()
        compressed = gzip.compress(data, compresslevel=3) if file.suffix != '.pdf' else data
        gzipped = len(compressed) < len(data)
        conn.execute(statement, (key, user_id, file.relative_to(directory).as_posix(),
                                 compressed if gzipped else data, gzipped, len(data)))


def files_in(directory):
    return [file for file in directory.rglob('*')
            if file.is_file() and not any(part.startswith('.') for part in file.relative_to(directory).parts)]


def persist_portfolio(directory, files=None, user_id=None, *, school_key=None, create=False):
    user_id = user_id or owner.get()
    if user_id is None:
        return
    with portfolio_lock, connect() as conn:
        save_portfolio_files(conn, user_id, directory, files if files is not None else files_in(directory),
                             school_key=school_key, create=create)


def hydrate_portfolios(user_id, root):
    """Populate the parser cache only with changed files belonging to this account."""
    import re

    with portfolio_lock, connect() as conn:
        rows = conn.execute(
            'SELECT portfolio_key, path, updated_at FROM public.web_portfolio_files WHERE owner=%s', (user_id,),
        ).fetchall()
        for row in rows:
            namespaced_key = row['portfolio_key']
            school = namespaced_key.rsplit(':', 1)[-1]
            relative = PurePosixPath(row['path'])
            if (not re.fullmatch(r'[a-f0-9]{64}', school) or relative.is_absolute()
                    or not relative.parts or any(part.startswith('.') or ':' in part or '\\' in part for part in relative.parts)):
                continue
            target = root / 'portfolios' / school / Path(*relative.parts)
            if portfolio_versions.get(target) == row['updated_at'] and target.is_file():
                continue
            item = conn.execute(
                'SELECT data, gzipped, updated_at FROM public.web_portfolio_files '
                'WHERE owner=%s AND portfolio_key=%s AND path=%s', (user_id, namespaced_key, row['path']),
            ).fetchone()
            if item is None:
                continue
            data = gzip.decompress(item['data']) if item['gzipped'] else item['data']
            target.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(dir=target.parent, delete=False) as temp:
                temp.write(data)
                staged = Path(temp.name)
            try:
                staged.replace(target)
            finally:
                staged.unlink(missing_ok=True)
            portfolio_versions[target] = item['updated_at']


def verify_schema():
    with connect() as conn:
        tables = conn.execute(
            "SELECT to_regclass('public.web_login_sessions') AS logins, "
            "to_regclass('public.interview_sessions') AS interviews, "
            "to_regclass('public.interview_units') AS units, "
            "to_regclass('public.interview_questions') AS questions, "
            "to_regclass('public.answers') AS answers, "
            "to_regclass('public.reports') AS reports, "
            "to_regclass('public.completeness_items') AS completeness, "
            "to_regclass('public.consistency_findings') AS consistency, "
            "to_regclass('public.documents') AS documents, "
            "to_regclass('public.document_blocks') AS blocks, "
            "to_regclass('public.events') AS events, "
            "to_regclass('public.event_sources') AS event_sources, "
            "to_regclass('public.retrieval_chunks') AS retrieval, "
            "to_regclass('public.question_bank') AS question_bank, "
            "to_regtype('vector') AS vector_type, "
            "to_regclass('public.web_interview_records') AS legacy_interviews, "
            "to_regclass('public.web_portfolio_files') AS portfolios, "
            "to_regclass('public.point_transactions') AS points, EXISTS("
            "SELECT 1 FROM information_schema.columns WHERE table_schema='public' "
            "AND table_name='users' AND column_name='point_balance') AS balance"
        ).fetchone()
        if not all(tables.values()):
            raise RuntimeError('The MAINSU PostgreSQL tables are incomplete.')


if __name__ == '__main__':
    try:
        verify_schema()
    except Exception as error:
        raise SystemExit(f'Neon verification failed ({type(error).__name__}).') from None
    print('Neon connection and MAINSU tables verified.')
