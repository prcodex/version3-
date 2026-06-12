# Economic Calendar Module

## TRIGGER
Upcoming or recently-released data: CPI, PPI, NFP, GDP, PMI (ISM, S&P Global), retail sales, jobless claims, JOLTS, durable goods, central bank decisions (Fed/ECB/BoE/BoJ/BCB), housing, consumer sentiment.

## SOURCES
- **Calendar Agent (Investing.com, 30-min lag)** — primary for upcoming releases.
- **@DeItaone** for actuals + market reaction at print time.
- **Bloomberg / WSJ / FT** for economist post-release takes.
- **Goldman / JPM / UBS** for pre-release forecasts when in feed.
- **DELTAONE DAILY DIGEST** for pre-computed T+0→T+5 price moves around top releases.

## RULES
- Always cite: date+time in **UTC-3**, forecast, actual (if released), previous, deviation.
- Impact: HIGH (CPI/NFP/Fed/ECB) / MED (PMI/retail/JOLTS) / LOW (claims/housing).
- Group by day; top of day = most market-moving.
- After release: actual vs forecast, deviation, first-5min market reaction (Digest data).
- Never invent calendar events. Nothing scheduled in the window → say so explicitly.
- Time conversion: EST + 2h = UTC-3 (08:30 EST → 10:30 UTC-3).
- Fed decisions defer to `fomc.md`; this module surfaces the data calendar around them.

## OUTPUT
`<pre>` table: Time (UTC-3) | Release | Actual | Forecast | Previous | Impact
