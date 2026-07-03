# sourcing/ — libretto toolchain for Merjack's live data (M5)

This is a self-contained Node project, separate from the Python `merjack/` package. Its job is
to **discover BizBuySell's listing API** with [libretto](https://libretto.sh), so that data
can be ported to a pure-Python `merjack/sources/bizbuysell_api.py` that implements the existing
`DealSource` interface. No LLM runs in Merjack's runtime sourcing path; libretto is a dev-time
discovery tool.

See `../docs/DESIGN.md` §8 for how this fits the overall architecture.

## Status (2026-06-22)
- libretto + Playwright Chromium installed and working **headless in this environment**
  (verified with `src/workflows/scrape-page.ts` against example.com).
- Config: `.libretto/config.json` (gitignored). Skill docs: `.claude/skills/libretto/`.
- BizBuySell recon: **not started.** Gated on (1) the ToS decision (BizBuySell prohibits
  automated access; the operator's call) and (2) anti-bot, which may block headless Chromium.

## Prerequisites
- Node (this repo verified on v25) and the local install in this folder (`npm install` already done).
- Chromium is already downloaded by `npx libretto setup`.

## Command reference (the ones we use)
```bash
npx libretto open <url> --headed --session bbs   # open a live page you can watch/interact with
npx libretto snapshot --session bbs              # screenshot + accessibility tree of the page
npx libretto exec --session bbs "await page.url()"   # prototype a step in the page context
npx libretto run src/workflows/<file>.ts --headless  # run/verify a workflow file
npx libretto close --session bbs                 # close the session when done
```
Session logs land in `.libretto/sessions/<session>/`:
- `network.jsonl` — captured xhr/fetch/document requests (+ `raw-network/` response bodies)
- `actions.jsonl` — clicks/fills/navigations
Query them with `jq`. Example, find JSON responses:
```bash
jq 'select(.contentType|test("json")) | {method,status,url,responseBodyPath}' .libretto/sessions/bbs/network.jsonl
```

## BizBuySell recon runbook (operator-driven)
Do this only if you accept the ToS posture. Keep it minimal and human-paced.

1. Read libretto's `.claude/skills/libretto/references/site-security-review.md` and apply it to BizBuySell first.
2. Enter at a user-facing URL on a cold session (deep links on a cold session are commonly bot-blocked):
   `npx libretto open https://www.bizbuysell.com --headed --session bbs`
3. In the visible browser, apply your filters (state, price, cash flow, industry) like a normal user. Solve any CAPTCHA/Cloudflare challenge in the window.
4. Once results render, inspect the network log for the call that returns the listing data as JSON (look in `network.jsonl` for an xhr/fetch with a JSON body containing listings). Read a body with:
   `gunzip -c .libretto/sessions/bbs/raw-network/<id>.response.json.gz | jq .`
5. If a clean JSON endpoint exists and is not blocked, note its URL, method, query params, and required headers/cookies. That is the contract for the Python client.
6. `npx libretto close --session bbs`.

## Handing off to Merjack
Bring back the endpoint shape (URL, params, a sample JSON response). The Python side then gets:
- `merjack/sources/bizbuysell_api.py` — an httpx client that calls those endpoints, with defensive
  pacing and the SQLite listing cache, normalizing the response into `merjack.models.Listing`.
- Tests against a captured sample response (no live network), like the other sources.

If anti-bot blocks the endpoint approach, fall back to manual import (already shipped) or a
licensed third-party API. The `DealSource` abstraction makes either a drop-in.
```
