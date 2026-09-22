"""
STRUCTURED DATA.

Spreadsheets are loaded into SQLite and queried exactly. They are never chunked
into the vector store, because chunking separates a header from its rows and
loses the structure that makes a table worth having. RAG is for prose.

    load_workbooks(folder)        -> [{"table", "rows", "columns"}]
    schema()                      -> text description of every table
    run_query(sql)                -> {"columns", "rows"} or {"error"}

Every table carries a `sensitivity` column, so the clearance filter applies here
exactly as it does to documents.
"""

import pathlib
import re
import sqlite3

DB_PATH = "./data.db"

# Only SELECT. Nothing may write, drop, attach or execute.
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|"
    r"replace|vacuum|reindex|truncate)\b", re.I)


def _connect():
    return sqlite3.connect(DB_PATH)


def _table_name(filename: str) -> str:
    stem = pathlib.Path(filename).stem.lower()
    return re.sub(r"[^a-z0-9_]", "_", stem)


def _column_name(header) -> str:
    return re.sub(r"[^a-z0-9_]", "_", str(header).strip().lower()).strip("_")


# ------------------------------------------------------------------ loading

def _register_sheet(name, level, rows):
    """Spreadsheets need an effective date too - a correction may contradict
    one as readily as a manual."""
    try:
        import registry
        registry.register(name, level, text=" ".join(str(r) for r in rows[:40]),
                          kind="table")
    except Exception:
        pass


def load_one(path: str, sensitivity: str = "internal") -> dict:
    """Load one spreadsheet into its own table. Replaces any previous version."""
    from openpyxl import load_workbook

    p = pathlib.Path(path)
    wb = load_workbook(p, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {"table": None, "rows": 0, "columns": []}

    headers = [_column_name(h) for h in rows[0] if h is not None]
    body = [r for r in rows[1:] if any(v is not None for v in r)]

    table = _table_name(p.name)
    cols = headers + ["sensitivity", "source_file"]

    con = _connect()
    cur = con.cursor()
    cur.execute('DROP TABLE IF EXISTS "%s"' % table)
    coldefs = ", ".join('"%s" TEXT' % c for c in cols)
    cur.execute('CREATE TABLE "%s" (%s)' % (table, coldefs))

    placeholders = ", ".join("?" for _ in cols)
    for r in body:
        values = [str(v) if v is not None else "" for v in r[:len(headers)]]
        values += [""] * (len(headers) - len(values))
        cur.execute('INSERT INTO "%s" VALUES (%s)' % (table, placeholders),
                    values + [sensitivity, p.name])

    con.commit()
    con.close()
    return {"table": table, "rows": len(body), "columns": headers,
            "sensitivity": sensitivity, "source_file": p.name}


def load_workbooks(folder: str = "corpus") -> list:
    """Load every spreadsheet in a folder. Classification comes from policy.yaml."""
    from policy import level_of

    out = []
    for p in sorted(pathlib.Path(folder).glob("*.xlsx")):
        if p.name.startswith("~$"):
            continue
        out.append(load_one(str(p), level_of(p.name)))
    return out


# ------------------------------------------------------------------ reading

def tables(user_level: str = "restricted") -> list:
    """Tables this clearance may query."""
    from policy import allowed_levels

    allowed = allowed_levels(user_level)
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    names = [r[0] for r in cur.fetchall()]

    out = []
    for t in names:
        cur.execute(f'SELECT sensitivity, source_file, COUNT(*) FROM "{t}"')
        row = cur.fetchone()
        if not row or row[0] not in allowed:
            continue
        cur.execute(f'PRAGMA table_info("{t}")')
        cols = [c[1] for c in cur.fetchall()
                if c[1] not in ("sensitivity", "source_file")]
        out.append({"table": t, "columns": cols, "rows": row[2],
                    "sensitivity": row[0], "source_file": row[1]})
    con.close()
    return out


def schema(user_level: str = "restricted") -> str:
    """Table descriptions for the model's prompt. Empty string if none."""
    ts = tables(user_level)
    if not ts:
        return ""
    lines = []
    for t in ts:
        lines.append(f'  {t["table"]} ({", ".join(t["columns"])})'
                     f'   {t["rows"]} rows, from {t["source_file"]}')
    return "\n".join(lines)


def run_query(sql: str, user_level: str = "restricted", limit: int = 50) -> dict:
    """Run a read-only query, restricted to tables this clearance may see."""
    from policy import allowed_levels

    sql = (sql or "").strip().rstrip(";")
    if not sql:
        return {"error": "No query given."}
    if FORBIDDEN.search(sql):
        return {"error": "Only SELECT queries are permitted."}
    if not re.match(r"^\s*select\b", sql, re.I):
        return {"error": "The query must begin with SELECT."}

    allowed = allowed_levels(user_level)
    permitted = {t["table"] for t in tables(user_level)}
    if not permitted:
        return {"error": "No tables are available at your clearance."}

    # Any table named in the query must be one this clearance may see.
    named = set(re.findall(r'\bfrom\s+"?([a-z0-9_]+)"?', sql, re.I))
    named |= set(re.findall(r'\bjoin\s+"?([a-z0-9_]+)"?', sql, re.I))
    blocked = named - permitted
    if blocked:
        return {"error": f"Not available at your clearance: {', '.join(blocked)}"}

    con = _connect()
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(sql)
        rows = cur.fetchmany(limit)
        columns = [d[0] for d in cur.description]
        data = [[r[c] for c in columns] for r in rows]
    except Exception as e:
        con.close()
        return {"error": str(e)}
    con.close()

    return {"columns": columns, "rows": data, "count": len(data), "sql": sql}


if __name__ == "__main__":
    for r in load_workbooks("corpus"):
        print(f'  {r["source_file"]:<32} -> {r["table"]}  '
              f'{r["rows"]} rows  [{r["sensitivity"]}]')
    print("\nschema:")
    print(schema("restricted"))
    print("\nsample query:")
    q = ("SELECT equipment, COUNT(*) AS failures, SUM(CAST(downtime_hours AS INT)) "
         "AS hours FROM maintenance_workbook WHERE type='Breakdown' "
         "GROUP BY equipment ORDER BY failures DESC")
    print(" ", run_query(q))
