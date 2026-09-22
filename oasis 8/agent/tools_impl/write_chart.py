"""Tool: draw a chart from the spreadsheets. STATE-CHANGING - writes a file.

The data comes from run_query, the same clearance-filtered path query_data
uses, so a table above the caller's level cannot be charted any more than it
can be read. The model supplies SQL and a chart type; it never supplies the
numbers, and it never touches the file system.

Column order carries the meaning, deliberately:
    first column  -> labels   (category, month, equipment tag)
    second column -> values   (the number being plotted)
Anything further is ignored. Asking a small model to nominate axes by name
invites it to name a column that is not there; ordering cannot be got wrong in
that way.
"""

import matplotlib
matplotlib.use("Agg")          # headless - must precede the pyplot import,
                               # or it tries to open a window from the server
import matplotlib.pyplot as plt

from agent.tools_impl._common import OUTPUT_DIR, output_name

KINDS = ("bar", "line", "pie", "barh")

# Muted, readable on both light and dark, and colour is never the only cue -
# every slice and bar is labelled.
PALETTE = ["#4b6bfb", "#e0823d", "#3aa675", "#c2504d", "#8a63d2",
           "#d4a017", "#5b8fa8", "#a0616a"]


def _clean(rows, columns):
    """Return (labels, values) or raise ValueError with a usable message."""
    if not rows:
        raise ValueError("The query returned no rows, so there is nothing "
                         "to chart.")
    if len(columns) < 2:
        raise ValueError("A chart needs two columns: a label column and a "
                         "number column. Add one to the SELECT.")

    labels, values = [], []
    for r in rows:
        # run_query returns rows as lists, positional against `columns`
        value = r[1]
        if value is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            raise ValueError(f"Column '{columns[1]}' holds text, not numbers. "
                             f"Put the number in the second column.")
        labels.append(str(r[0]))

    if not values:
        raise ValueError("Every value was empty, so there is nothing to plot.")
    if len(values) > 25:
        raise ValueError(f"{len(values)} rows is too many to read on a chart. "
                         f"Group them or add a LIMIT.")
    return labels, values


def tool_write_chart(sql: str = "", kind: str = "bar", title: str = "",
                     user_level: str = "public", filename: str = None,
                     **_ignored):
    from structured import run_query

    kind = (kind or "bar").lower().strip()
    if kind not in KINDS:
        return {"error": f"Chart type '{kind}' is not available. "
                         f"Use one of: {', '.join(KINDS)}."}

    result = run_query(sql, user_level)
    if result.get("error"):
        return result                      # clearance and SELECT-only refusals

    try:
        labels, values = _clean(result.get("rows", []),
                                result.get("columns", []))
    except ValueError as e:
        return {"error": str(e)}

    colours = [PALETTE[i % len(PALETTE)] for i in range(len(values))]
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=150)

    if kind == "pie":
        total = sum(values)
        ax.pie(values, labels=labels, colors=colours, startangle=90,
               autopct=lambda p: f"{p:.0f}%" if p >= 4 else "",
               textprops={"fontsize": 9})
        ax.axis("equal")
        ax.set_title(title or "", fontsize=12, pad=14)
        caption = f"total {total:,.0f}"
    else:
        if kind == "line":
            ax.plot(labels, values, marker="o", linewidth=2,
                    color=PALETTE[0])
        elif kind == "barh":
            ax.barh(labels, values, color=colours)
        else:
            ax.bar(labels, values, color=colours)

        # The number on the bar. A chart nobody can read a value off is a
        # picture, not a finding.
        if kind in ("bar", "barh"):
            for i, v in enumerate(values):
                if kind == "bar":
                    ax.text(i, v, f"{v:,.0f}", ha="center", va="bottom",
                            fontsize=8.5)
                else:
                    ax.text(v, i, f" {v:,.0f}", ha="left", va="center",
                            fontsize=8.5)

        ax.set_title(title or "", fontsize=12, pad=12)
        # A one-letter SQL alias ("n", "c") is noise on an axis; drop it.
        ylab = result["columns"][1].replace("_", " ").strip()
        if len(ylab) > 2:
            ax.set_ylabel(ylab[0].upper() + ylab[1:], fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=8.5)
        if kind != "barh" and max((len(l) for l in labels), default=0) > 7:
            plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        caption = f"{len(values)} rows"

    fig.tight_layout()
    name = output_name("chart", "png", filename)
    fig.savefig(OUTPUT_DIR / name, bbox_inches="tight")
    plt.close(fig)

    return {"ok": True, "written": True, "file": name, "kind": kind,
            "rows": len(values), "labels": labels[:8],
            "message": f"{name} written ({kind} chart, {caption})."}
