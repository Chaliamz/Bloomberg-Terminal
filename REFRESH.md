# Unattended refresh runbook

This is the procedure a scheduled run follows. It exists so an unattended
session has a deterministic path instead of re-deriving the whole system each
time. Follow it in order and do not skip the gate.

## What this environment can and cannot do (verified, not assumed)

- **No outbound egress to any market or news host.** The proxy gateway answers
  403 to CONNECT for coinglass, coinank, coinalyze, binance, coingecko,
  cryptodatadownload, investing.com, macrotrends, treasury.gov — everything
  tested so far, including `fonts.googleapis.com`. `curl` and `WebFetch` both
  fail. **`WebSearch` is the only channel.** Do not waste a run re-testing every
  host; one spot check is enough to notice if the policy ever opens up.
- WebSearch returns model-synthesised summaries, not pages. So: attribute every
  number to a **named carrier**, and when the carrier cannot be narrowed to one
  page, tier it as an aggregate and say so.
- Fortune publishes one citable article per day at
  `https://fortune.com/article/price-of-bitcoin-MM-DD-2026/` and states its own
  Eastern time in the copy. **The time varies per article** (4:00–9:00 a.m. ET
  observed). Take the stamp from the article, never assume one. Aug–Sep 2026 is
  EDT, so ET + 4h = UTC.
- A published artifact cannot fetch (CSP blocks fetch/XHR/WebSocket). The page
  ships an honestly stamped snapshot whose age counter climbs.

## Procedure

### 1. Find what is new

Search for BTC prints later than the newest one already held:

```bash
python3 -c "from macro import seed; a=seed.build().price_anchors; print(a[-1].date, a[-1].price, a[-1].source)"
```

Then `WebSearch` for the days after that. Also sweep for market-moving news:
rates, energy, geopolitics, central banks, large-cap equities.

### 2. Store what you found — never edit `macro/seed.py` from a scheduled run

```bash
python3 -m macro observe \
  --date 2026-09-07T12:00:00Z --price 79812.44 \
  --source "Fortune" --tier 3 \
  --url "https://fortune.com/article/price-of-bitcoin-09-07-2026/" \
  --note "8:00 a.m. ET print."
```

The store (`state/observations.json`) is append-only, validating and
de-duplicating. It **refuses** a missing source or tier, a malformed or future
stamp, and a non-finite or non-positive price. A re-scan that finds the same
print again is a no-op, and a scan that finds nothing changes nothing — that is
the intended outcome of a quiet hour, not a failure.

**If a scan finds nothing new, stop here.** Do not republish, do not commit, and
do not manufacture an update. An unchanged page is the correct output of an hour
in which nothing happened.

### 3. Regenerate

```bash
rm -f state/snapshot.json && python3 -m macro terminal
```

The cached snapshot must be removed or the render silently reuses the old data.

### 4. Run the gate — all of it

```bash
python3 -m unittest discover -s tests -t .
python3 tools/verify_terminal.py
python3 tools/verify_board.py
```

All three must pass. If any fails, **fix it and re-run**; do not publish a red
build. If it cannot be fixed in the run, leave the artifact untouched and say
what broke.

### 5. Look at it

Screenshot the heatmap and check it renders. A passing assertion is not a
substitute for seeing the page.

### 6. Publish and commit

Republish to the **existing** artifact URL so the link the user holds keeps
working:

```
https://claude.ai/code/artifact/7dd21161-ff98-423b-9887-3b90d2d51f8b
```

Publish `board/macro-desk-fragment.html`, passing that URL as `url`. Read the
artifact first, then publish onto what comes back — never create a new one.

Then commit and push to `claude/macro-intelligence-radar-6fpk1q`.

## The contract this must not break

- Every number carries source, tier, unit and timestamp.
- A source that cannot be reached **never** restamps existing data.
- Never interpolate price between observations. Gaps are shown, not filled.
- Corrections are recorded in `CONFLICTS`, never silently overwritten.
- Data age is measured from the **newest observation**, not from when the scan
  ran, so a scan that fetched nothing cannot make the page look fresh.
