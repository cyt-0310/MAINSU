"""Durable, one-time portfolio submissions for the local MAINSU web app."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
import json
import logging
from pathlib import Path
import re
import subprocess
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory
from threading import Lock
import unicodedata

import pypdfium2 as pdfium
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from ai_services import prepare
from bridge import load_portfolio_events
from evidence import SentenceEmbedder
from interview_gap_detection.llm_client import get_client, get_model
from web_accounts import workspace
import web_postgres as pg

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 5 * 1024 * 1024
SLOTS = {'statement': 1, 'activities': 10, 'coursework': 3}
MAX_FILES = sum(SLOTS.values())
POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix='portfolio')
JOBS = {}
LOCK = Lock()
PDF_LOCK = Lock()
STATUS_LOCK = Lock()
log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def embedding_model():
    return SentenceEmbedder('shibing624/text2vec-base-chinese')


def response(payload, status=200):
    return JSONResponse(payload, status_code=status, headers={'Cache-Control': 'no-store'})


def clean_target(value):
    if not isinstance(value, str):
        raise ValueError('請填寫學校及科系。')
    value = ' '.join(unicodedata.normalize('NFKC', value).split())
    if not value or len(value) > 100 or any(unicodedata.category(c).startswith('C') for c in value):
        raise ValueError('請輸入有效的學校及科系名稱（各 100 字以內）。')
    return value


def school_id(school, department):
    names = [''.join(value.casefold().replace('臺', '台').split()) for value in (school, department)]
    return sha256(json.dumps(names, ensure_ascii=False).encode()).hexdigest()


def path_for(key):
    if not re.fullmatch(r'[a-f0-9]{64}', key):
        raise FileNotFoundError(key)
    return workspace.get() / 'portfolios' / key


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, payload):
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def portfolio_record(directory):
    record = read_json(directory / 'submission.json')
    with LOCK:
        job = JOBS.get(directory)
        running = job is not None and not job.done()
        status = get_status(directory)
        if status['status'] in ('queued', 'parsing', 'analyzing') and not running:
            status = {'status': 'failed', 'message': '分析已中斷，請用原本的檔案重試。'}
    return {**record, **status}


def document_path(directory, document):
    source = document.get('source')
    if source:
        return directory.parent / source['portfolio'] / (source['file'] + '.pdf')
    return directory / (document['id'] + '.pdf')


def save_submission(school, department, documents):
    key = school_id(school, department)
    directory = path_for(key)
    if directory.exists():
        raise FileExistsError(directory)
    # Existing immutable submissions can share the original PDF, even if the
    # student chooses to upload the same bytes rather than selecting a reference.
    known = {}
    for manifest_path in directory.parent.glob('*/submission.json'):
        for entry in read_json(manifest_path).get('files', []):
            original = document_path(manifest_path.parent, entry)
            if original.is_file():
                known.setdefault(sha256(original.read_bytes()).digest(),
                                 {'portfolio': original.parent.name, 'file': original.stem})
    documents = [(category, name, data, source or known.get(sha256(data).digest()))
                 for category, name, data, source in documents]
    for _, name, data, source in documents:
        try:
            with PDF_LOCK:
                with pdfium.PdfDocument(BytesIO(data)) as pdf:
                    if len(pdf) == 0:
                        raise ValueError('Empty PDF')
        except (pdfium.PdfiumError, ValueError) as error:
            raise ValueError(f'「{name}」無法開啟，請確認 PDF 未損毀且未加密。') from error
    directory.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.upload-', dir=directory.parent) as temp:
        staged = Path(temp) / 'submission'
        staged.mkdir()
        manifest = []
        for number, (category, name, data, source) in enumerate(documents, 1):
            file_id = str(number)
            entry = {'id': file_id, 'category': category, 'name': name, 'size': len(data)}
            digest = sha256(data).digest()
            source = source or known.get(digest)
            if source:
                entry['source'] = source
            else:
                (staged / f'{file_id}.pdf').write_bytes(data)
                known[digest] = {'portfolio': key, 'file': file_id}
            manifest.append(entry)
        write_json(staged / 'submission.json', {
            'id': key, 'school': school, 'department': department, 'files': manifest,
            'submittedAt': datetime.now(timezone.utc).isoformat(),
        })
        set_status(staged, 'queued', '等待分析')
        pg.persist_portfolio(staged, school_key=key, create=True)
        try:
            staged.rename(directory)
        except OSError:
            if not directory.exists():
                raise
            if pg.owner.get() is None:
                raise FileExistsError(directory) from None
    queue_analysis(directory)
    return portfolio_record(directory)


def set_status(directory, status, message, user_id=None):
    path = directory / 'status.json'
    status_data = {'status': status, 'message': message}
    with STATUS_LOCK:
        write_json(path, status_data)
        if user_id is not None:
            pg.persist_portfolio(directory, [path], user_id)


def get_status(directory):
    with STATUS_LOCK:
        return read_json(directory / 'status.json')


def queue_analysis(directory):
    user_id = pg.owner.get()
    with LOCK:
        current = JOBS.get(directory)
        if current is not None and not current.done():
            return
        if get_status(directory)['status'] == 'ready':
            return
        set_status(directory, 'queued', '等待分析', user_id)
        JOBS[directory] = POOL.submit(analyze, directory, user_id)


def analyze(directory, user_id=None):
    record = read_json(directory / 'submission.json')
    parsed = []
    try:
        for number, document in enumerate(record['files'], 1):
            name = document['name']
            set_status(directory, 'parsing', f'解析 PDF（{number}/{len(record["files"])}）', user_id)
            original = document_path(directory, document)
            destination = original.parent / f'parsed-{original.stem}'
            if not destination.exists():
                with TemporaryDirectory(prefix='.parse-', dir=directory) as temp:
                    output = Path(temp) / 'parsed'
                    subprocess.run([
                        sys.executable, '-X', 'utf8', str(ROOT / 'docling_pdf' / 'parse_pdf.py'),
                        str(original), '--output', str(output),
                    ], check=True, timeout=600, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    load_portfolio_events(next(output.glob('*.events.json')))
                    output.rename(destination)
            if user_id is not None:
                pg.persist_portfolio(original.parent, pg.files_in(destination), user_id)
            portfolio = load_portfolio_events(next(destination.glob('*.events.json')))
            portfolio['pdf_name'] = f'{document["id"]} · {name}' if sum(
                entry['name'] == name for entry in record['files']
            ) > 1 else name
            parsed.append(portfolio)
    except Exception:
        log.exception('Portfolio PDF parsing failed')
        set_status(directory, 'failed', f'無法解析「{name}」。請確認這份 PDF 有可辨識的文字，再試一次。', user_id)
        return
    set_status(directory, 'analyzing', '整理事件、建立檢索資料與面試題目', user_id)
    try:
        get_model()
        get_client()
    except RuntimeError as error:
        set_status(directory, 'failed', f'PDF 已解析。{error}', user_id)
        return
    try:
        prepared = directory / 'prepared'
        if not prepared.exists():
            with TemporaryDirectory(prefix='.analysis-', dir=directory) as temp:
                output = Path(temp) / 'prepared'
                prepare(parsed, embedding_model(), output, department=record['department'])
                output.rename(prepared)
        if user_id is not None:
            pg.persist_portfolio(directory, pg.files_in(prepared), user_id)
            from question_rotation import portfolio_identity
            from postgres_portfolio import save_parsed_portfolio

            identity = portfolio_identity(directory)
            if not identity:
                raise ValueError('Unable to identify the parsed portfolio')
            with pg.connect() as conn:
                portfolio_id = pg.ensure_portfolio(conn, user_id, record, identity)
                save_parsed_portfolio(conn, user_id, portfolio_id, record, parsed, prepared, pg.jsonb)
    except Exception:
        log.exception('Portfolio event analysis failed')
        set_status(directory, 'failed', 'PDF 已解析，無法完成事件整理或出題。請確認 AI 服務及模型設定後重試。', user_id)
        return
    set_status(directory, 'ready', '分析完成', user_id)


async def portfolios(request):
    if request.headers.get('sec-fetch-site') == 'cross-site':
        return response({'error': '請從 MAINSU 網頁操作。'}, 403)
    if request.method in ('GET', 'HEAD'):
        records = [portfolio_record(path.parent) for path in (workspace.get() / 'portfolios').glob('*/submission.json')]
        return response(sorted(records, key=lambda record: record['submittedAt'], reverse=True))
    try:
        if int(request.headers.get('content-length', '0')) > MAX_FILES * LIMIT + 65536:
            return response({'error': '備審檔案超過總大小限制。'}, 413)
        async with request.form(max_files=MAX_FILES, max_fields=3) as form:
            school = clean_target(form.get('school'))
            department = clean_target(form.get('department'))
            if any(key not in {*SLOTS, 'school', 'department', 'reuse'} for key in form):
                raise ValueError('備審資料有未支援的欄位。')
            documents = []
            references = json.loads(form.get('reuse', '[]'))
            if not isinstance(references, list) or len(references) > MAX_FILES:
                raise ValueError('選用的檔案資料不正確。')
            for slot, maximum in SLOTS.items():
                uploads = form.getlist(slot)
                selected = [r for r in references if isinstance(r, dict) and r.get('category') == slot]
                if len(uploads) + len(selected) > maximum or (slot == 'statement' and not (uploads or selected)):
                    raise ValueError('學習歷程自述必須 1 份，多元表現最多 10 份，課程學習成果最多 3 份。')
                for upload in uploads:
                    if not isinstance(upload, UploadFile):
                        raise ValueError('備審需為 PDF。')
                    name = Path((upload.filename or '').replace('\\', '/')).name.strip()
                    data = await upload.read(LIMIT + 1)
                    if not name.lower().endswith('.pdf') or len(name) > 200 or not data.startswith(b'%PDF-') or len(data) > LIMIT:
                        raise ValueError('每份備審必須是有效 PDF，大小上限為 5 MB。')
                    documents.append((slot, name, data, None))
                for ref in selected:
                    origin = path_for(ref.get('portfolio', ''))
                    original = next((f for f in read_json(origin / 'submission.json')['files']
                                     if f['id'] == ref.get('file') and f['category'] == slot), None)
                    if original is None:
                        raise ValueError('找不到選用的備審檔案。')
                    source = original.get('source') or {'portfolio': origin.name, 'file': original['id']}
                    documents.append((slot, original['name'], document_path(origin, original).read_bytes(), source))
        return response(await run_in_threadpool(save_submission, school, department, documents), 201)
    except FileExistsError:
        return response({'error': '此校系已提交備審，可在校系列表查看。'}, 409)
    except (ValueError, HTTPException, FileNotFoundError) as error:
        return response({'error': error.detail if isinstance(error, HTTPException) else str(error)}, 400)


async def portfolio_action(request):
    if request.headers.get('sec-fetch-site') == 'cross-site':
        return response({'error': '請從 MAINSU 網頁操作。'}, 403)
    try:
        directory = path_for(request.path_params['portfolio_id'])
        record = portfolio_record(directory)
    except FileNotFoundError:
        return response({'error': '找不到此校系的備審。'}, 404)
    if request.method == 'POST':
        await run_in_threadpool(queue_analysis, directory)
        return response(portfolio_record(directory), 202)
    file_id = request.path_params.get('file_id')
    file = next((file for file in record['files'] if file['id'] == file_id), None)
    if file is None:
        return response({'error': '找不到此檔案。'}, 404)
    return FileResponse(document_path(directory, file), filename=file['name'], media_type='application/pdf',
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


routes = [
    Route('/api/portfolios', portfolios, methods=['GET', 'POST']),
    Route('/api/portfolios/{portfolio_id}/retry', portfolio_action, methods=['POST']),
    Route('/api/portfolios/{portfolio_id}/files/{file_id}', portfolio_action),
]
