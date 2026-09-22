"""Tool: query the structured data. READ-ONLY.

Spreadsheets live in SQLite, not in the vector store. A question like "how many
breakdowns in 2025" is a filter and a count, not a similarity search - chunking
a table separates the header from its rows and answers such questions badly.

The clearance filter applies here too: a table above the caller's level is not
queryable, and the model is only ever shown the schema of tables it may reach.
"""


def tool_query_data(sql: str, user_level: str = "public", **_ignored):
    from structured import run_query
    return run_query(sql, user_level)
