import json
import sys
import time
import urllib.request
import urllib.error

BASE = "https://api.exa.ai"
TIMEOUT = 15
RETRIES = 3


def _exit_for(status: int) -> int:
    if status in (401, 403):
        return 3
    if status == 429:
        return 4
    if 500 <= status < 600:
        return 6
    return 2


def post(path: str, payload: dict, api_key: str) -> dict:
    url = BASE + path
    data = json.dumps(payload).encode()
    last = "network error"
    for attempt in range(1, RETRIES + 1):
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "User-Agent": "exa-cli/0.1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:2000]
            code = e.code
            if code == 429 or code >= 500:
                last = f"HTTP {code}: {body}"
                if attempt < RETRIES:
                    retry_after = e.headers.get("Retry-After", "1") if e.headers else "1"
                    try:
                        wait = min(int(retry_after), 30)
                    except ValueError:
                        wait = attempt
                    print(f"attempt {attempt}/{RETRIES} HTTP {code}, retrying in {wait}s",
                          file=sys.stderr)
                    time.sleep(wait)
                    continue
                print(f"attempts exhausted: {attempt}/{RETRIES}", file=sys.stderr)
                raise SystemExit(_exit_for(code)) from None
            print(f"error: HTTP {code}: {body}", file=sys.stderr)
            raise SystemExit(_exit_for(code)) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = f"network error: {e}"
            if attempt < RETRIES:
                print(f"attempt {attempt}/{RETRIES} {last}, retrying",
                      file=sys.stderr)
                time.sleep(attempt)
                continue
            print(f"error: {last}", file=sys.stderr)
            raise SystemExit(5) from None
    print(f"error: {last}", file=sys.stderr)
    raise SystemExit(5)
