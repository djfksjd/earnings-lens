"""공용 HTTP 클라이언트: 타임아웃·재시도·에러 마스킹."""
from __future__ import annotations

import time

import requests

from ..security import redact

TIMEOUT = 15
_session = requests.Session()


class ProviderError(RuntimeError):
    """사용자에게 보여줘도 안전한(키가 지워진) 메시지만 담는다."""


def get(url: str, *, params: dict | None = None, headers: dict | None = None,
        retries: int = 2, timeout: int = TIMEOUT) -> requests.Response:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = _session.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 429 and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:  # 메시지에 URL(키 포함)이 들어갈 수 있다
            last = e
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
    raise ProviderError(redact(f"{type(last).__name__}: {last}"))


def post(url: str, *, json: dict, headers: dict | None = None, timeout: int = TIMEOUT) -> requests.Response:
    try:
        r = _session.post(url, json=json, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        raise ProviderError(redact(f"{type(e).__name__}: {e}")) from None
