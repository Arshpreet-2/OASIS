"""
DOCUMENT REGISTRY — what the library knows about each document beyond its text.

Today a document's identity is its filename and its classification lives in
policy.yaml. That is enough to answer "who may read this" and not enough to
answer "is this still current", which is the question a correction has to
settle: a correction may only override a document it is newer than.

So each document carries an EFFECTIVE DATE — the date on the document itself,
not the day it was ingested. A 2019 manual uploaded last week is still a 2019
manual.

Three sources, in order, and which one applied is recorded:

    stated     an administrator typed it. Believed over everything else.
    document   read out of the text, and only from an unambiguous pattern.
               A wrong date that looks confident is worse than no date, so
               anything doubtful falls through rather than being guessed at.
    default    DEFAULT_EFFECTIVE below, when neither of the above supplied one.

The provenance is shown in the Documents tab, so nobody mistakes a fallback
for a real date, and a precedence decision can always be explained.
"""

import datetime
import json
import pathlib
import re

REGISTRY = pathlib.Path("registry.json")

# Used when a document states no date and nobody has set one. A seeded value,
# not an assertion about the document - hence the separate provenance.
DEFAULT_EFFECTIVE = "2026-07-01"

MONTHS = ("january february march april may june july august september "
          "october november december").split()

# Only unambiguous forms. Deliberately narrow: a missed date falls back and is
# labelled as a fallback; a misread one silently changes which source wins.
PATTERNS = [
    re.compile(r"\b(20\d\d)-(\d{2})-(\d{2})\b"),                       # ISO
    re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(20\d\d)\b"),         # 2 Sep 2026
    re.compile(r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(20\d\d)\b"),       # Sep 2, 2026
]


def _load() -> dict:
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text())
        except Exception:
            return {}
    return {}


def _save(data: dict):
    REGISTRY.write_text(json.dumps(data, indent=2, sort_keys=True))


def date_in_text(text: str) -> str:
    """The latest unambiguous date in the text, or "".

    Latest rather than first: a maintenance log's header says what period it
    covers, and its last entry is what makes it current.
    """
    found = []
    for pattern in PATTERNS:
        for m in pattern.finditer(text or ""):
            parts = m.groups()
            try:
                if pattern is PATTERNS[0]:
                    y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
                elif pattern is PATTERNS[1]:
                    d, name, y = int(parts[0]), parts[1].lower(), int(parts[2])
                    mo = next((i + 1 for i, n in enumerate(MONTHS)
                               if n.startswith(name[:3])), 0)
                else:
                    name, d, y = parts[0].lower(), int(parts[1]), int(parts[2])
                    mo = next((i + 1 for i, n in enumerate(MONTHS)
                               if n.startswith(name[:3])), 0)
                if mo:
                    found.append(datetime.date(y, mo, d))
            except (ValueError, TypeError):
                continue          # not a real date; ignore rather than guess
    # Ignore dates in the future. A HAZOP lists action due dates, and taking
    # the latest date in the text picked one of those as the report's own -
    # a real date, confidently wrong, which is the failure this whole field
    # exists to avoid.
    today = datetime.date.today()
    found = [d for d in found if d <= today]
    return max(found).isoformat() if found else ""


def register(document: str, sensitivity: str, text: str = "",
             stated: str = None, kind: str = "document") -> dict:
    """Record a document and settle its effective date. Returns its entry."""
    data = _load()
    existing = data.get(document, {})

    if stated:
        effective, source = stated, "stated"
    elif existing.get("date_source") == "stated":
        effective, source = existing["effective"], "stated"   # do not overwrite
    else:
        found = date_in_text(text)
        if found:
            effective, source = found, "document"
        else:
            effective, source = DEFAULT_EFFECTIVE, "default"

    data[document] = {
        "document": document,
        "sensitivity": sensitivity,
        "kind": kind,
        "effective": effective,
        "date_source": source,
        "ingested": datetime.date.today().isoformat(),
    }
    _save(data)
    return data[document]


def set_date(document: str, effective: str) -> bool:
    """An administrator states the date. Believed over anything extracted."""
    data = _load()
    if document not in data:
        return False
    data[document]["effective"] = effective
    data[document]["date_source"] = "stated"
    _save(data)
    return True


def get(document: str) -> dict:
    return _load().get(document, {})


def effective_of(document: str) -> str:
    """The effective date, or "" if the document is not registered."""
    return _load().get(document, {}).get("effective", "")


def all_entries() -> dict:
    return _load()


def forget(document: str):
    data = _load()
    if data.pop(document, None) is not None:
        _save(data)
