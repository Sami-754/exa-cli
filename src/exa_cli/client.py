import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import urlencode

BASE = "https://api.exa.ai"
TIMEOUT = 15
RETRIES = 3


def _exit_for(status: int) -> int:
    if status in (401, 403, 404):
        return 3
    if status == 429:
        return 4
    if 500 <= status < 600:
        return 6
    return 2


def _handle_error(resp=None, e=None, body=None, code=None, attempt=None):
    if e is not None:
        body = e.read().decode(errors="replace")[:2000]
        code = e.code
    if code == 429 or code >= 500:
        if attempt is not None and attempt < RETRIES:
            retry_after = (e.headers.get("Retry-After", "1") if e is not None and e.headers else "1")
            try:
                wait = min(int(retry_after), 30)
            except ValueError:
                wait = attempt if attempt else 1
            print(f"attempt {attempt}/{RETRIES} HTTP {code}, retrying in {wait}s",
                  file=sys.stderr)
            time.sleep(wait)
            return True
        print(f"attempts exhausted: {RETRIES}/{RETRIES}", file=sys.stderr)
        raise SystemExit(_exit_for(code)) from None
    print(f"error: HTTP {code}: {body}", file=sys.stderr)
    raise SystemExit(_exit_for(code)) from None


def _do(method: str, path: str, payload: dict | None, api_key: str) -> dict:
    url = BASE + path
    data = json.dumps(payload).encode() if method == "POST" or payload is not None else None
    for attempt in range(1, RETRIES + 1):
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "User-Agent": "exa-cli/0.1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw.strip().startswith(("{", "[")) else {"raw": raw}
        except urllib.error.HTTPError as e:
            if _handle_error(e=e, attempt=attempt):
                continue
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"attempt {attempt}/{RETRIES} network error: {e}, retrying", file=sys.stderr)
            if attempt >= RETRIES:
                print(f"error: network error: {e}", file=sys.stderr)
                raise SystemExit(5) from None
            time.sleep(attempt)
            continue
    raise SystemExit(5)


def post(path: str, payload: dict, api_key: str) -> dict:
    return _do("POST", path, payload, api_key)


def get(path: str, api_key: str, params: dict | None = None) -> dict:
    if params:
        qs = urlencode({k: v for k, v in params.items() if v is not None})
        if qs:
            path = f"{path}?{qs}"
    return _do("GET", path, None, api_key)


def patch(path: str, payload: dict, api_key: str) -> dict:
    return _do("PATCH", path, payload, api_key)


def delete(path: str, api_key: str) -> dict:
    return _do("DELETE", path, None, api_key)
