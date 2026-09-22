"""Tool: produce a spreadsheet. STATE-CHANGING - needs approval."""

import datetime

from agent.tools_impl._common import OUTPUT_DIR, output_name


def tool_write_xlsx(title: str, headers: list, rows: list = None,
                    filename: str = None, author: str = "",
                    sources: list = None, **_ignored):
    """Produce a spreadsheet. STATE-CHANGING - needs approval first."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = (title or "Data")[:31]

    ws.append(headers or [])
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows or []:
        ws.append(r)

    for col in ws.columns:
        width = max((len(str(c.value or "")) for c in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(width + 3, 48)

    name = output_name("data", "xlsx", filename)
    path = OUTPUT_DIR / name
    wb.save(path)
    return {"file": name, "path": str(path)}
