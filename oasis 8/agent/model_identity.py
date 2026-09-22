"""Real model identity for the sovereignty panel.

"qwen3:4b" is not an answer to "what produced this answer?" - the name says
nothing about which build is loaded, or whether the file is the one the site
approved. Ollama identifies every model layer by SHA-256 digest, so the digest
is available and is the honest thing to display.

Read once at startup. If Ollama cannot be reached the digest is reported as
unknown rather than invented.
"""

import hashlib

from agent.config import MODELS, OLLAMA_BASE_URL

_CACHE = {}


def _installed() -> dict:
    """{model name: digest} from Ollama's /api/tags.

    Read over plain HTTP rather than through the client library: the library's
    show() has a strict response schema that varies between versions and does
    not surface the digest at all. The HTTP API has carried it throughout.
    """
    import json
    import urllib.request

    with urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=4) as r:
        data = json.loads(r.read().decode())

    out = {}
    for m in data.get("models", []):
        name = m.get("name") or m.get("model") or ""
        digest = str(m.get("digest", "")).replace("sha256:", "")
        if name:
            out[name] = digest
    return out


def model_digests() -> dict:
    """{role: {"model": name, "digest": "abc123def456" or ""}} for each
    configured model. Cached - the files do not change while the server runs.

    A model that is not pulled reports an empty digest. Nothing is invented.
    """
    if _CACHE:
        return _CACHE

    try:
        installed = _installed()
    except Exception:
        installed = {}

    for role, name in MODELS.items():
        digest = installed.get(name, "")
        if not digest and ":" not in name:
            digest = installed.get(f"{name}:latest", "")
        _CACHE[role] = {"model": name, "digest": digest[:12]}
    return _CACHE


def summary() -> str:
    """One short string for the panel: the general model's digest, or a plain
    statement that it could not be read. Never a placeholder."""
    d = model_digests().get("general", {})
    return d.get("digest") or "unavailable"
