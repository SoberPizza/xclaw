"""Chrome tab management via Chrome DevTools Protocol (CDP)."""

import json
import urllib.request
import urllib.parse
from urllib.error import URLError

from xclaw.config import CDP_HOST, CDP_PORT


def _cdp_url(path: str) -> str:
    return f"http://{CDP_HOST}:{CDP_PORT}{path}"


def list_tabs() -> dict:
    """List all open Chrome page tabs via CDP."""
    try:
        with urllib.request.urlopen(_cdp_url("/json/list"), timeout=3) as resp:
            raw = json.loads(resp.read())
    except (URLError, OSError) as exc:
        return {"status": "error", "message": f"cannot connect to Chrome CDP at {CDP_HOST}:{CDP_PORT} — {exc}"}

    tabs = []
    for entry in raw:
        if entry.get("type") != "page":
            continue
        url = entry.get("url", "")
        domain = urllib.parse.urlparse(url).hostname or ""
        tabs.append({
            "id": entry["id"],
            "title": entry.get("title", ""),
            "url": url,
            "domain": domain,
        })

    return {"status": "ok", "tabs": tabs}


def switch_tab(domain: str) -> dict:
    """Activate the first Chrome tab whose domain contains *domain*."""
    result = list_tabs()
    if result["status"] != "ok":
        return result

    for tab in result["tabs"]:
        if domain.lower() in tab["domain"].lower():
            target_id = tab["id"]
            try:
                urllib.request.urlopen(_cdp_url(f"/json/activate/{target_id}"), timeout=3)
            except (URLError, OSError) as exc:
                return {"status": "error", "message": f"cannot connect to Chrome CDP at {CDP_HOST}:{CDP_PORT} — {exc}"}
            return {
                "status": "ok",
                "action": "switch_tab",
                "id": target_id,
                "title": tab["title"],
                "url": tab["url"],
                "domain": tab["domain"],
            }

    return {"status": "error", "message": f"no tab matching '{domain}'"}
