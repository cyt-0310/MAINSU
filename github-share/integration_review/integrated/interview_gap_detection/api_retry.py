"""Bounded transient retries with a scoped interview-clock notification."""
from contextlib import contextmanager
from contextvars import ContextVar
import random
import time


class TemporaryServiceError(RuntimeError):
    def __init__(self, message, status_code=503):
        super().__init__(message)
        self.status_code = status_code


_excluded_time = ContextVar('api_retry_excluded_time', default=None)
_progress = ContextVar('api_retry_progress', default=None)


@contextmanager
def retry_progress(callback):
    token = _progress.set(callback)
    try:
        yield
    finally:
        _progress.reset(token)


def notify_progress(provider, state, **details):
    callback = _progress.get()
    if callback:
        callback(dict(provider=provider, state=state, **details))


@contextmanager
def retry_clock(callback):
    token = _excluded_time.set(callback)
    try:
        yield
    finally:
        _excluded_time.reset(token)


def retry_transient(operation, max_retries=3, provider=None):
    """Retry marked service failures at 2, 4 and 8 seconds; never retry invalid outputs."""
    for attempt in range(max_retries + 1):
        started = time.monotonic()
        try:
            if provider:
                notify_progress(provider, 'requesting', attempt=attempt)
            return operation()
        except TemporaryServiceError as error:
            try:
                if attempt == max_retries:
                    raise
                delay = min(8, 2 ** (attempt + 1))
                if provider:
                    notify_progress(provider, 'retrying', attempt=attempt+1, delay=delay, code=error.status_code)
                print(f'服務暫時無法使用（HTTP {error.status_code}），'
                      f'{delay:.1f} 秒後自動重試（{attempt + 1}/{max_retries}）……', flush=True)
                time.sleep(delay)
            finally:
                callback = _excluded_time.get()
                if callback:
                    callback(time.monotonic() - started)
