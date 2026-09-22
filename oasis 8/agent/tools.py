"""
THE TOOL REGISTRY.

One file per tool in agent/tools_impl/. This file only says which tools exist,
what arguments they take, and - the part that matters - whether each one
CHANGES STATE.

    changes_state: False   runs immediately
    changes_state: True    never executed by the agent; proposed for approval

To add a tool: write agent/tools_impl/<name>.py, import it below, add a row.
Nothing else in the system needs to change.
"""

from agent.tools_impl._common import OUTPUT_DIR                       # noqa: F401
from agent.tools_impl.search import tool_search
from agent.tools_impl.calculate import tool_calculate
from agent.tools_impl.query_data import tool_query_data
from agent.tools_impl.describe_table import tool_describe_table
from agent.tools_impl.write_docx import tool_write_docx
from agent.tools_impl.write_pptx import tool_write_pptx
from agent.tools_impl.write_xlsx import tool_write_xlsx
from agent.tools_impl.write_chart import tool_write_chart
from agent.tools_impl.run_code import tool_run_code
from agent.tools_impl.templates import find_template, TEMPLATE_FOR    # noqa: F401


TOOLS = {
    "search_documents": {
        "fn": tool_search,
        "changes_state": False,
        "args": "question (string)",
        "describe": lambda a: f"search the library for \"{a.get('question','')}\"",
        "help": "Find passages in the document library. Use this first, always.",
    },
    "calculate": {
        "fn": tool_calculate,
        "changes_state": False,
        "args": "expression (arithmetic only, e.g. \"(187+246+188+94)/4\")",
        "describe": lambda a: f"calculate {a.get('expression','')}",
        "help": "Do arithmetic exactly. Never compute in your head.",
    },
    "query_data": {
        "fn": tool_query_data,
        "changes_state": False,
        "args": "sql (a SELECT query against the tables listed above)",
        "describe": lambda a: f"query the data: {a.get('sql','')[:60]}",
        "help": ("Query the spreadsheets exactly with SQL. Use this for counts, "
                 "totals, averages and filters over tabular data - never search "
                 "for those, and never add them up yourself."),
    },
    "describe_table": {
        "fn": tool_describe_table,
        "changes_state": False,
        "args": "table (optional - the table name)",
        "describe": lambda a: f"profile the table {a.get('table','')}".strip(),
        "help": ("See what is inside a spreadsheet before querying it: row "
                 "count, and for each column its type, how many distinct "
                 "values, the range of numbers and dates, and the commonest "
                 "categories. Use this FIRST when asked to analyse, explore or "
                 "summarise a sheet, or whenever you do not know what the "
                 "values look like."),
    },
    "run_code": {
        "fn": tool_run_code,
        "changes_state": True,
        "args": ('code (python that prints its result), sql (optional - a '
                 'SELECT whose rows are written to /work/data.csv for the '
                 'code to read)'),
        "describe": lambda a: "run python in the sandbox",
        "help": ("Run Python in an isolated container to obtain a RESULT the user asked for. Never use it to answer a request for code itself - that is written in the reply. Never use it to draw a chart - write_chart does that. Use ONLY for analysis "
                 "that SQL cannot express - a trend line, a correlation, a "
                 "distribution, a forecast. If a SELECT can answer it, use "
                 "query_data instead. Supply sql to have the rows waiting at "
                 "/work/data.csv; read it with the csv module. Only the "
                 "standard library is available - no pandas, no numpy. Print "
                 "what you want reported; nothing else is returned."),
    },
    "write_chart": {
        "fn": tool_write_chart,
        "changes_state": True,
        "args": ('sql (a SELECT returning TWO columns: labels first, numbers '
                 'second), kind ("bar", "line", "pie" or "barh"), '
                 'title (string)'),
        "describe": lambda a: f"draw a {a.get('kind','bar')} chart"
                              f" titled \"{a.get('title','')}\"",
        "help": ("Draw a chart from the spreadsheets. The SELECT must return "
                 "exactly two columns - the label first, the number second. "
                 "Alias the number column to something readable - "
                 "SUM(cost_rs) AS \"Cost (Rs.)\" - because that alias becomes the axis label. "
                 "Use it when a comparison across categories or a trend over "
                 "time is easier to see than to read."),
    },
    "write_docx": {
        "fn": tool_write_docx,
        "changes_state": True,
        "args": "title (string), body (string), filename (optional)",
        "describe": lambda a: f"write {a.get('filename') or 'a Word document'}"
                              f" titled \"{a.get('title','')}\"",
        "help": "Produce a Word document such as an approval note or report.",
    },
    "write_pptx": {
        "fn": tool_write_pptx,
        "changes_state": True,
        "args": ('title (string), subtitle (string), '
                 'slides (list of {"heading": string, "bullets": [string]})'),
        "describe": lambda a: f"write {a.get('filename') or 'a presentation'}"
                              f" titled \"{a.get('title','')}\"",
        "help": ("Produce a PowerPoint deck, such as a board presentation or a "
                 "briefing. Give each slide a heading and three or four bullets."),
    },
    "write_xlsx": {
        "fn": tool_write_xlsx,
        "changes_state": True,
        "args": "title (string), headers (list), rows (list of lists)",
        "describe": lambda a: f"write {a.get('filename') or 'a spreadsheet'}",
        "help": "Produce a spreadsheet from tabular data.",
    },
}


def catalogue() -> str:
    """The tool list, as text for the model's prompt."""
    out = []
    for name, t in TOOLS.items():
        flag = "  [needs approval]" if t["changes_state"] else ""
        out.append(f"- {name}({t['args']}){flag}\n    {t['help']}")
    return "\n".join(out)
