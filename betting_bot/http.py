"""Tiny stdlib HTTP helper (honours HTTPS_PROXY via urllib)."""
import json
import time
import urllib.error
import urllib.request

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (betting-bot)",
    "Accept": "application/json",
}


class FetchError(RuntimeError):
    pass


def get_json(url, headers=None, retries=3, timeout=20):
    hdrs = dict(DEFAULT_HEADERS)
    hdrs.update(headers or {})
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise FetchError(f"Could not fetch {url}: {last}")
