"""
CORRECTIONS — how the library learns when an answer is wrong.

The tempting design is a corrections table the model consults. Do not build
that. It creates a second source of knowledge outside policy.yaml, outside the
clearance filter and outside the citation trail — and a correction written from
a restricted document would then reach everyone, unlabelled.

So a correction is a classified, cited, clearance-filtered record like any
other, and it is stored rather than trained:

    anyone may raise one         spotting an error is not a privileged act
    an administrator reviews it  and sets its sensitivity, as on upload
    a different person approves  the submitter may not approve their own
    it enters the index          filtered by clearance like any passage
    it is cited by name          with its approver and date, never blended
    deleting it reverts          which is the argument for storing, not
                                 training: a mistaken correction is one
                                 record removed

PRECEDENCE. A correction outranks the document it corrects ONLY if it is newer
than that document's effective date. Otherwise a correction approved in March
would silently override a manual revised in June. Where the document has no
date the organisation's default applies, and which date was used is recorded
so the decision can be explained.
"""

import datetime
import json
import pathlib
import secrets

STORE = pathlib.Path("corrections.json")

PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"


def _load() -> dict:
    if STORE.exists():
        try:
            return json.loads(STORE.read_text())
        except Exception:
            return {}
    return {}


def _save(data: dict):
    STORE.write_text(json.dumps(data, indent=2, sort_keys=True))


def raise_correction(question: str, answer: str, what_is_wrong: str,
                     correct_answer: str, by: str, sources: list = None,
                     corrects: str = "") -> dict:
    """Anyone may raise one, whatever their clearance. Nothing changes yet."""
    data = _load()
    cid = f"cor_{len(data) + 1}_{secrets.token_hex(3)}"
    data[cid] = {
        "id": cid,
        "status": PENDING,
        "question": question,
        "answer_given": answer,
        "what_is_wrong": what_is_wrong,
        "correct_answer": correct_answer,
        "corrects": corrects,                 # filename it contradicts, if any
        "sources_used": sources or [],
        "raised_by": by,
        "raised_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "sensitivity": None,                  # set by the approver
        "approved_by": None,
        "approved_at": None,
        "reason": None,
    }
    _save(data)
    return data[cid]


def review(cid: str, approve: bool, by: str, sensitivity: str = None,
           edited_answer: str = None, reason: str = "") -> dict:
    """Approve or reject. The approver must not be the submitter.

    Enforced here rather than in the interface: a control that only exists in
    the browser is not a control.
    """
    data = _load()
    item = data.get(cid)
    if not item:
        return {"ok": False, "error": "No such correction."}
    if item["status"] != PENDING:
        return {"ok": False, "error": f"Already {item['status']}."}
    if item["raised_by"] == by:
        return {"ok": False,
                "error": "A correction must be approved by someone other "
                         "than the person who raised it."}

    if not approve:
        item.update(status=REJECTED, approved_by=by, reason=reason,
                    approved_at=datetime.datetime.now().isoformat(
                        timespec="seconds"))
        _save(data)
        return {"ok": True, "status": REJECTED, "correction": item}

    if not sensitivity:
        return {"ok": False,
                "error": "Set a clearance level before approving. A "
                         "correction is a document and must be classified."}

    if edited_answer:
        item["correct_answer"] = edited_answer
    item.update(status=APPROVED, approved_by=by, sensitivity=sensitivity,
                approved_at=datetime.datetime.now().isoformat(
                    timespec="seconds"))
    _save(data)
    return {"ok": True, "status": APPROVED, "correction": item}


def approved_for(user_level: str) -> list:
    """Approved corrections this clearance may see."""
    from policy import allowed_levels

    allowed = allowed_levels(user_level)
    return [c for c in _load().values()
            if c["status"] == APPROVED and c.get("sensitivity") in allowed]


def pending() -> list:
    return [c for c in _load().values() if c["status"] == PENDING]


def all_corrections() -> list:
    return sorted(_load().values(), key=lambda c: c["raised_at"], reverse=True)


def supersedes(correction: dict) -> tuple:
    """(wins, why). Does this correction outrank the document it corrects?"""
    import registry

    doc = correction.get("corrects")
    if not doc:
        return True, "corrects no particular document"

    doc_date = registry.effective_of(doc)
    if not doc_date:
        return True, f"{doc} is not registered"

    approved = (correction.get("approved_at") or "")[:10]
    if not approved:
        return False, "not approved"

    if approved > doc_date:
        return True, f"approved {approved}, after {doc} dated {doc_date}"
    return False, (f"{doc} was revised {doc_date}, after this correction was "
                   f"approved {approved} - the document is newer")


def relevant(question: str, user_level: str, limit: int = 3) -> list:
    """Approved corrections that bear on this question and still hold.

    Matched on shared words rather than embeddings: corrections are few, and a
    second index to keep in step with the first is a liability. Revisit if the
    count ever grows into the hundreds.
    """
    words = {w for w in question.lower().split() if len(w) > 3}
    if not words:
        return []

    scored = []
    for c in approved_for(user_level):
        wins, why = supersedes(c)
        if not wins:
            continue
        target = (c["question"] + " " + c["correct_answer"]).lower()
        overlap = sum(1 for w in words if w in target)
        if overlap >= 2:
            scored.append((overlap, c, why))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"correction": c, "why": why} for _, c, why in scored[:limit]]
