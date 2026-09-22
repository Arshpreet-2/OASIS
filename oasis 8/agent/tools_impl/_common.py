"""Shared by every tool file."""

import datetime
import pathlib
import secrets

OUTPUT_DIR = pathlib.Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


def output_name(stem: str, ext: str, given: str = None) -> str:
    """A name that cannot collide.

    Time alone is not enough: two people approving a document in the same
    second produced the same filename, the second write overwrote the first,
    and ownership of the file silently transferred with it. A short random
    suffix removes that entirely.
    """
    if given:
        return pathlib.Path(given).name          # never a path
    stamp = f"{datetime.datetime.now():%H%M%S}"
    return f"{stem}_{stamp}_{secrets.token_hex(2)}.{ext}"
