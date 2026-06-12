"""Deterministic Telegram renderer for structured geo responses.

Haiku generates JSON under schemas/geo_response.schema.json via Bedrock
constrained decoding; this module renders it to Telegram HTML. Format
compliance (pre tables, no pipes, <4000 chars) lives HERE, in code —
not in prompt rules the model can break.
"""
from __future__ import annotations

MAX_CHARS = 4000


def _pre_table(rows: list[list[str]], headers: list[str], width: int = 35) -> str:
    cols = list(zip(*([headers] + rows))) if rows else [headers]
    widths = [min(max(len(str(c)) for c in col), 12) for col in cols]
    def fmt(row):
        return " ".join(str(c)[:w].ljust(w) for c, w in zip(row, widths)).rstrip()
    lines = [fmt(headers)] + [fmt(r) for r in rows]
    return "<pre>\n" + "\n".join(l[:width] if False else l for l in lines) + "\n</pre>"


def render_geo(d: dict) -> str:
    out: list[str] = [f"<b>{d.get('window', '')}</b>"]

    if d.get("timeline"):
        out.append("<b>TIMELINE</b>")
        out += [f"• {e['time_brt']} — {e['event']} ({e['source']})" for e in d["timeline"]]

    if d.get("actors"):
        out.append("<b>ACTORS</b>")
        out += [f"• <b>{a['actor']}</b>: {a['summary']}" for a in d["actors"]]

    if d.get("market_reaction"):
        out.append("<b>MARKET REACTION</b>")
        rows = [[m["asset"], m["before"], m["after"], m["change_pct"]] for m in d["market_reaction"]]
        out.append(_pre_table(rows, ["Asset", "Before", "After", "Chg"]))

    if d.get("experts"):
        out.append("<b>EXPERT ANALYSIS</b>")
        for e in d["experts"]:
            line = f"• <b>{e['name']}</b> ({e['source_date']}): {e['take']}"
            if e.get("disagrees_with"):
                line += f" [disagrees with {e['disagrees_with']}]"
            out.append(line)

    if d.get("prediction_markets"):
        out.append("<b>PREDICTION MARKETS</b>")
        rows = [[p["market"], p["price"], p["trend"]] for p in d["prediction_markets"]]
        out.append(_pre_table(rows, ["Market", "Price", "Trend"]))
    # absent/empty => total silence, enforced structurally

    if d.get("watch"):
        out.append("<b>WHAT TO WATCH (24h)</b>")
        out += [f"{i}. {w['trigger']} → {w['market_implication']}"
                for i, w in enumerate(d["watch"], 1)]

    text = "\n".join(out)
    if len(text) > MAX_CHARS:  # hard Telegram guard, trim watch/experts first
        text = text[: MAX_CHARS - 1] + "…"
    return text
