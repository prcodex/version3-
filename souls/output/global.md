# Output Format (Telegram — Global)
- Rich markdown: bold, bullets, headers allowed.
- Structured data (prices, polls, calendar, odds): `<pre>` blocks, aligned columns, max 35 chars wide. Narrative stays OUTSIDE `<pre>`.
- NEVER: markdown pipe tables, ASCII art/sparklines, raw JSON, decorative characters.
- Every time-windowed summary ends with a MARKETS `<pre>` snapshot: S&P, Oil, Gold, DXY, 10Y + assets impacted by the news (LIVE data).
- Inline event-to-price anchoring: "Shah field fire — Brent +2.1% at $92.40." Template: "EVENT at TIME → ASSET $BEFORE→$AFTER (±%) — WHY."
