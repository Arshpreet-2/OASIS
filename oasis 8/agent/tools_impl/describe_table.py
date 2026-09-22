"""Tool: profile a table. READ-ONLY.

The model is told the column NAMES in its prompt, but nothing about the values -
how many distinct pieces of equipment, what the date range is, how cost is
spread. So an open request like "analyse the maintenance sheet" leaves it
guessing what is worth querying, and a small model guessing costs turns.

One call returns the shape of the data: row count, and per column its type,
distinct count, range for numbers and dates, and the commonest values for
categories. From there its follow-up queries are informed rather than
speculative.

Clearance applies as everywhere else: a table above the caller's level is not
profiled, because the shape of a table is information about its contents.
"""

TOP_VALUES = 6          # enough to see the pattern, short enough to read
MAX_DISTINCT = 15       # above this it is an identifier, not a category


def _looks_like_dates(values) -> bool:
    """A date column is a range, not a set of categories."""
    import re
    if not values:
        return False
    pattern = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")
    return all(pattern.match(str(v).strip()) for v in values[:20])


def tool_describe_table(table: str = "", user_level: str = "public",
                        **_ignored):
    import sqlite3
    from structured import _connect, tables

    permitted = {t["table"]: t for t in tables(user_level)}
    if not permitted:
        return {"error": "No tables are available at your clearance."}

    name = (table or "").strip().strip('"')
    if not name:
        if len(permitted) == 1:
            name = next(iter(permitted))
        else:
            return {"error": f"Name the table. Available: "
                             f"{', '.join(sorted(permitted))}."}
    if name not in permitted:
        return {"error": f"Not available at your clearance: {name}. "
                         f"Available: {', '.join(sorted(permitted))}."}

    con = _connect()
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute(f'SELECT COUNT(*) FROM "{name}"')
    rows = cur.fetchone()[0]

    cur.execute(f'PRAGMA table_info("{name}")')
    columns = [c[1] for c in cur.fetchall()
               if c[1] not in ("sensitivity", "source_file")]

    profile = []
    for col in columns:
        cur.execute(f'SELECT COUNT(DISTINCT "{col}") FROM "{name}"')
        distinct = cur.fetchone()[0]

        # Numeric if every non-empty value converts. SQLite is loosely typed
        # and spreadsheets arrive as text, so ask the data, not the schema.
        cur.execute(f'SELECT "{col}" FROM "{name}" WHERE "{col}" IS NOT NULL')
        vals = [r[0] for r in cur.fetchall()]
        numeric = bool(vals)
        for v in vals:
            try:
                float(v)
            except (TypeError, ValueError):
                numeric = False
                break

        entry = {"column": col, "distinct": distinct}
        if numeric:
            nums = [float(v) for v in vals]
            entry["kind"] = "number"
            entry["min"] = min(nums)
            entry["max"] = max(nums)
            entry["total"] = round(sum(nums), 2)
            entry["mean"] = round(sum(nums) / len(nums), 2)
        elif _looks_like_dates(vals):
            cur.execute(f'SELECT MIN("{col}"), MAX("{col}") FROM "{name}"')
            lo, hi = cur.fetchone()
            entry["kind"] = "date"
            entry["earliest"] = lo
            entry["latest"] = hi
        elif distinct >= rows and rows > 1:
            # One distinct value per row: an identifier, not a category.
            # Listing "each appears once" fifteen times tells nobody anything.
            cur.execute(f'SELECT MIN("{col}"), MAX("{col}") FROM "{name}"')
            lo, hi = cur.fetchone()
            entry["kind"] = "identifier"
            entry["first"] = lo
            entry["last"] = hi
        elif distinct <= MAX_DISTINCT:
            cur.execute(f'SELECT "{col}", COUNT(*) FROM "{name}" '
                        f'GROUP BY "{col}" ORDER BY 2 DESC LIMIT {TOP_VALUES}')
            entry["kind"] = "category"
            entry["top"] = [{"value": r[0], "count": r[1]}
                            for r in cur.fetchall()]
        else:
            cur.execute(f'SELECT MIN("{col}"), MAX("{col}") FROM "{name}"')
            lo, hi = cur.fetchone()
            entry["kind"] = "text"
            entry["first"] = lo
            entry["last"] = hi
        profile.append(entry)

    con.close()
    return {"table": name, "rows": rows, "columns": profile,
            "source_file": permitted[name]["source_file"]}
