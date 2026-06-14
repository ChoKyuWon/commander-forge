#!/usr/bin/env python3
"""Query CommanderSalt (the remote-oracle) for a deck's power level — no login required.

Pipeline (reverse-engineered from the SPA; see references/remote-oracle.md):
  1. POST https://api.commandersalt.com/decks?url=<deckUrl>   -> {"id": <contentHash>, ...}  (triggers ingest)
  2. GET  https://api.commandersalt.com/decks?id=<id>         -> powerLevelRating, saltRating, comboRating, ...

Usage:
  python3 query_commandersalt.py --url https://archidekt.com/decks/23502978
  python3 query_commandersalt.py --archidekt-id 23502978
  python3 query_commandersalt.py --url <moxfield/archidekt/tappedout url> --json

On success the LAST stdout line is the power number (e.g. "9.02"); detail goes to stderr.
Exit codes: 0 ok | 2 bad usage | 4 ingest failed | 5 score never resolved (timeout).
Stdlib only.
"""
import argparse, json, sys, time, urllib.request, urllib.error, urllib.parse

API = "https://api.commandersalt.com"
UA = {"User-Agent": "commander-forge/1.0", "Content-type": "application/json;charset=UTF-8", "Accept": "application/json"}


def _req(method, url, timeout=60):
    r = urllib.request.Request(url, method=method, headers=UA)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            body = json.loads(resp.read().decode() or "{}")
            # The API is expected to return a JSON object; coerce anything else
            # (array, scalar, null) to {} so downstream .get() never throws.
            return resp.status, (body if isinstance(body, dict) else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        return e.code, (parsed if isinstance(parsed, dict) else {"_raw": raw[:200]})
    except urllib.error.URLError as e:
        # Network/DNS/timeout error — return a sentinel status 0 so callers can
        # decide (ingest treats it as a hard failure; read treats it as transient).
        return 0, {"_error": str(getattr(e, "reason", e))}


def ingest(deck_url, old_deck_id=None):
    """POST the deck URL; returns the CommanderSalt content-hash id.

    If old_deck_id is given, append &oldDeckId=<id> to refresh that prior entry in
    place (the SPA's refresh path). That route is authenticated-only on
    CommanderSalt, so an anonymous refresh 404s — we transparently retry without
    it. CommanderSalt ids are a content hash, so an unchanged decklist returns the
    SAME id either way (no clutter); only a changed deck mints a new id.
    """
    base = f"{API}/decks?url={urllib.parse.quote(deck_url, safe='')}"
    if old_deck_id:
        url = f"{base}&oldDeckId={urllib.parse.quote(old_deck_id, safe='')}"
        status, body = _req("POST", url, timeout=90)
        if status == 200 and body.get("id"):
            return body["id"]
        print(f"  oldDeckId refresh unavailable (HTTP {status}); falling back to plain ingest "
              "(same decklist => same id, so no clutter)", file=sys.stderr)
    status, body = _req("POST", base, timeout=90)
    if status != 200 or not body.get("id"):
        raise RuntimeError(f"ingest HTTP {status}: {str(body)[:200]}")
    return body["id"]


def read_score(deck_id):
    """GET the scored deck.

    Returns the full rating dict when ready, or None when still processing (so the
    caller keeps polling). Raises RuntimeError on a TERMINAL error — e.g. a 4xx, or
    a CommanderSalt error string like "Deck URL invalid, or deck is not publicly
    visible" — so a permanently-bad deck fails fast (exit 4) instead of burning every
    poll and reporting a misleading timeout (exit 5). Status 0 (a transient network
    blip from _req) is treated as not-ready and retried.
    """
    url = f"{API}/decks?id={urllib.parse.quote(deck_id, safe='')}"
    status, body = _req("GET", url, timeout=30)
    if status == 0:
        return None  # transient network error — keep polling
    if status >= 400:
        raise RuntimeError(f"score read HTTP {status}: {str(body)[:200]}")
    st = body.get("status") if isinstance(body.get("status"), dict) else {}
    err = body.get("error") or st.get("error")
    if err and not body.get("powerLevelRating"):
        raise RuntimeError(f"CommanderSalt could not score the deck: {err}")
    if st.get("exists") and body.get("powerLevelRating") is not None:
        return body
    return None


def query(deck_url, attempts=15, delay=4, old_deck_id=None):
    cid = ingest(deck_url, old_deck_id=old_deck_id)
    print(f"commandersalt deck id: {cid}", file=sys.stderr)
    for i in range(attempts):
        d = read_score(cid)  # raises RuntimeError on a terminal error -> exit 4
        if d:
            return cid, d
        if i < attempts - 1:
            time.sleep(delay)  # don't sleep after the final poll
    raise TimeoutError(f"score not resolved after {attempts} polls; deck id {cid}")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--url", help="full deck URL (archidekt/moxfield/tappedout)")
    g.add_argument("--archidekt-id", help="numeric Archidekt deck id")
    ap.add_argument("--json", action="store_true", help="print the full rating JSON to stdout")
    ap.add_argument("--old-deck-id", help="prior CommanderSalt deck id to refresh in place "
                    "(authenticated-only on CommanderSalt; falls back to plain ingest on 404)")
    a = ap.parse_args()
    deck_url = a.url or f"https://archidekt.com/decks/{a.archidekt_id}"
    try:
        cid, d = query(deck_url, old_deck_id=a.old_deck_id)
    except RuntimeError as e:
        print(f"ERROR ingest: {e}", file=sys.stderr); return 4
    except TimeoutError as e:
        print(f"ERROR timeout: {e}", file=sys.stderr); return 5
    try:
        power = round(float(d["powerLevelRating"]), 2)
    except (TypeError, ValueError, KeyError) as e:
        print(f"ERROR: non-numeric powerLevelRating {d.get('powerLevelRating')!r} ({e})",
              file=sys.stderr); return 4
    if not 0 <= power <= 10:
        # The number is documented as a 0–10 scale; a value outside it usually means
        # CommanderSalt changed its scale/endpoint — warn so the caller can fall back.
        print(f"WARNING: power={power} is outside the expected 0–10 scale "
              "(CommanderSalt may have changed its API)", file=sys.stderr)
    print(f"power={power} | salt={round(d.get('saltRating',0),1)} "
          f"combo={round(d.get('comboRating',0),1)} threat={round(d.get('threatRating',0),1)} "
          f"| archetype={d.get('archetypeLabel','?')} | {d.get('colorIdentity','?')} {d.get('_cardCount','?')} cards "
          f"| https://commandersalt.com/details/deck/{cid}", file=sys.stderr)
    if a.json:
        out = {k: d.get(k) for k in
               ("powerLevelRating", "powerLevelDisplayValue", "saltRating", "comboRating",
                "threatRating", "archetypeLabel", "colorIdentity", "_cardCount")}
        out["commandersaltId"] = cid  # pass this back as --old-deck-id next iteration
        print(json.dumps(out))
    else:
        print(power)  # last line = the number, for easy capture
    return 0


if __name__ == "__main__":
    sys.exit(main())
