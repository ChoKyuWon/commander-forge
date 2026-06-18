#!/usr/bin/env python3
"""
Upload a commander-forge deck.txt to Archidekt automatically.

Uses Archidekt's (undocumented, reverse-engineered) web API. The endpoints and
payload shapes below were extracted from Archidekt's own frontend bundle; see
references/upload.md for provenance and a guide to fixing them if Archidekt
changes its API.

Pipeline (create):
  1. POST /api/rest-auth/login/         -> { token, refresh_token, user }
  2. (all writes) Authorization: JWT <token>
  3. POST /api/decks/v2/                 -> create empty deck, returns { id, ... }
  4. POST /api/cards/massDeckEdit/       -> server-side parse of the Archidekt
                                            text format ("archidekt" parser),
                                            returns resolved cards w/ Archidekt ids
  5. PATCH /api/decks/<id>/modifyCards/v2/ -> persist the resolved cards; the
                                            response maps patchId -> deckRelationId,
                                            saved to <deck>.archidekt.json (manifest)

Update-in-place (--update): reuse ONE deck across a loop without clutter.
  Reads the manifest (name -> {relationId, qty}), diffs vs the new deck.txt, then
  DELETE /api/decks/relations/<id>/ for removed/changed cards + modifyCards add for
  new/changed cards. Same deck id + URL (so CommanderSalt refreshes in place too).
  Falls back to create if no manifest exists. --dry-run shows the +/- plan only.

Auth comes from the environment:
  ARCHIDEKT_EMAIL, ARCHIDEKT_PASSWORD

Stdlib only (urllib) so the skill can run it without installing anything.

Exit codes:
  0  success (deck created + cards saved); prints the deck URL on the last line
  2  bad usage / missing input
  3  missing credentials
  4  login failed
  5  deck create failed
  6  card resolve/save failed (deck may exist but be empty/partial)

On any non-zero exit the caller (the skill) should fall back to telling the user
to import deck.txt manually.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = "https://archidekt.com"
LOGIN_URL = BASE + "/api/rest-auth/login/"
CREATE_URL = BASE + "/api/decks/v2/"
PARSE_URL = BASE + "/api/cards/massDeckEdit/"
MODIFY_URL = BASE + "/api/decks/{id}/modifyCards/v2/"
SETTINGS_URL = BASE + "/api/decks/{id}/update/"  # PATCH deck settings (name/visibility)
RELATION_URL = BASE + "/api/decks/relations/{rid}/"  # DELETE a single deck-card relation
MANIFEST_SUFFIX = ".archidekt.json"  # written next to deck.txt: {deckId,url,relations:{name:relId}}

# deckFormat enum from Archidekt frontend: EDH/Commander == 3
FORMAT_EDH = 3
FORMATS = {"edh": 3, "commander": 3, "custom": 0, "standard": 1}

DEFAULT_LABEL = ",#656565"  # matches the frontend's default colorLabel (name="", color)


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def _request(url, *, method="GET", token=None, body=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = "JWT " + token
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"_raw": raw[:500]}
        return e.code, parsed
    except urllib.error.URLError as e:
        return 0, {"_error": str(e.reason)}


# ---------------------------------------------------------------------------
# deck.txt handling
# ---------------------------------------------------------------------------

_CARD_LINE = re.compile(r"^\s*(\d+)x?\s+.+", re.IGNORECASE)


def read_deck(path):
    """Return (text, card_line_count). Validates it looks like an import file."""
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f]
    card_lines = [ln for ln in lines if ln.strip() and _CARD_LINE.match(ln)]
    if not card_lines:
        raise ValueError(f"{path} contains no recognizable card lines")
    # The Archidekt parser wants the raw text; keep only non-empty lines.
    text = "\n".join(ln for ln in lines if ln.strip())
    return text, len(card_lines)


def derive_name(deck_text, fallback="Commander Forge deck"):
    """Use the first [Commander]-tagged line's card name as the deck name."""
    for ln in deck_text.splitlines():
        if "[Commander]" in ln:
            m = re.match(r"^\s*\d+x?\s+(.+?)\s*(\(|\[).*$", ln)
            if m:
                return m.group(1).strip()
            m = re.match(r"^\s*\d+x?\s+(.+?)\s*$", ln)
            if m:
                return m.group(1).strip()
    return fallback


# ---------------------------------------------------------------------------
# API steps
# ---------------------------------------------------------------------------

def login(email, password):
    status, data = _request(LOGIN_URL, method="POST", body={"email": email, "password": password})
    if status != 200:
        detail = data.get("non_field_errors") or data.get("detail") or data
        log(f"  login HTTP {status}: {detail}")
        return None
    token = data.get("token") or data.get("access") or data.get("access_token") or data.get("key")
    if not token:
        log(f"  login succeeded but no token field found in response: {list(data)}")
        return None
    user = (data.get("user") or {}).get("username", "?")
    log(f"  logged in as {user}")
    return token


def create_deck(token, name, deck_format, bracket, private, unlisted):
    body = {
        "name": name,
        "deckFormat": deck_format,
        "edhBracket": bracket if deck_format == FORMAT_EDH else None,
        "description": "",
        "featured": "",
        "playmat": "",
        "private": bool(private),
        "unlisted": bool(unlisted),
        "theorycrafted": False,
        "game": None,
        "cardPackage": None,
        "extras": {
            "decksToInclude": [],
            "commandersToAdd": [],
            "forceCardsToSingleton": False,
            "ignoreCardsOutOfCommanderIdentity": True,
        },
    }
    status, data = _request(CREATE_URL, method="POST", token=token, body=body)
    if status not in (200, 201):
        log(f"  create HTTP {status}: {data}")
        return None
    deck_id = data.get("id")
    if not deck_id:
        log(f"  create returned no id: {data}")
        return None
    return deck_id


def resolve_cards(token, deck_text):
    """Call massDeckEdit to parse the Archidekt text into resolved card objects."""
    body = {"parser": "archidekt", "current": "", "edit": deck_text}
    status, data = _request(PARSE_URL, method="POST", token=token, body=body)
    if status not in (200, 201):
        log(f"  massDeckEdit HTTP {status}: {data}")
        return None
    syntax = data.get("syntaxErrors") or []
    carderr = data.get("cardErrors") or []
    if syntax:
        log(f"  WARNING {len(syntax)} syntax error(s): {syntax[:5]}")
    if carderr:
        log(f"  WARNING {len(carderr)} card(s) not found: {carderr[:10]}")
    return data


def _iter_resolved(parse_resp):
    """
    Yield resolved card dicts from the massDeckEdit response, tolerating a few
    possible shapes (toAdd list, or categories map of card lists). Each yielded
    item is normalized to: {cardid, categories, quantity, modifier}.
    """
    seen = []

    def emit(entry, category_hint=None):
        if not isinstance(entry, dict):
            return
        card = entry.get("card") if isinstance(entry.get("card"), dict) else entry
        cardid = (
            card.get("id")
            or card.get("cardId")
            or entry.get("cardId")
            or entry.get("cardid")
        )
        if not cardid:
            return
        cats = entry.get("categories") or card.get("categories") or []
        if isinstance(cats, str):
            cats = [cats]
        if not cats and category_hint:
            cats = [category_hint]
        qty = entry.get("quantity") or entry.get("qty") or card.get("qty") or 1
        modifier = entry.get("modifier") or "Normal"
        seen.append({
            "name": entry.get("name") or card.get("name") or "",
            "cardid": cardid,
            "categories": list(cats),
            "quantity": int(qty) or 1,
            "modifier": modifier,
            "customCardId": (entry.get("customCard") or {}).get("id"),
        })

    if isinstance(parse_resp.get("toAdd"), list):
        for entry in parse_resp["toAdd"]:
            emit(entry)
    if not seen and isinstance(parse_resp.get("categories"), dict):
        for cat_name, cat in parse_resp["categories"].items():
            cards = cat.get("cards") if isinstance(cat, dict) else cat
            if isinstance(cards, list):
                for entry in cards:
                    emit(entry, category_hint=cat_name)
    return seen


def add_cards(token, deck_id, resolved):
    """Add resolved cards to a deck. Returns name->deckRelationId map, or None on failure.

    The modifyCards/v2 response maps each patchId back to a deckRelationId — we keep
    those so the deck can be updated/removed later without re-reading the deck.
    """
    cards = []
    for i, r in enumerate(resolved):
        cards.append({
            "action": "add",
            "cardid": r["cardid"],
            "customCardId": r.get("customCardId"),
            "categories": r["categories"] or ["Default"],
            "patchId": str(i),
            "modifications": {
                "quantity": r["quantity"],
                "modifier": r["modifier"],
                "customCmc": None,
                "companion": False,
                "flippedDefault": False,
                "label": DEFAULT_LABEL,
            },
        })
    if not cards:
        log("  nothing resolved to add")
        return {}
    status, data = _request(
        MODIFY_URL.format(id=deck_id), method="PATCH", token=token, body={"cards": cards}
    )
    if status not in (200, 201):
        log(f"  modifyCards HTTP {status}: {data}")
        return None
    added = data.get("add")
    # A 200 with cards to add but no confirmed 'add' list means nothing was saved —
    # treat it as a failure (exit 6) rather than reporting a falsely-empty success.
    if not isinstance(added, list) or not added:
        log(f"  modifyCards 200 but no cards confirmed added (keys={list(data)}); "
            "treating as a save failure")
        return None
    rel = {}
    by_patch = {str(a.get("patchId")): a.get("deckRelationId") for a in added}
    for i, r in enumerate(resolved):
        rid = by_patch.get(str(i))
        if rid is not None and r.get("name"):
            rel[r["name"]] = {"rid": rid, "qty": r["quantity"]}
    log(f"  added {len(added)} card record(s)")
    if not rel:
        # Cards were saved on Archidekt, but the patchId->relation mapping failed, so
        # the manifest can't be built — a later --update will fall back to create.
        log("  WARNING: cards added but no manifest relations could be mapped "
            "(future --update will recreate instead of updating in place)")
    return rel


def delete_relation(token, rid):
    status, _ = _request(RELATION_URL.format(rid=rid), method="DELETE", token=token)
    return status in (200, 204)


def set_deck_settings(token, deck_id, private, unlisted, name=None):
    """PATCH a deck's settings in place (used on --update so re-uploads keep the
    intended visibility and name).

    Endpoint: PATCH /api/decks/<id>/update/  (the plain /api/decks/<id>/ route only
    allows GET/DELETE; settings live on /update/). Sets visibility always, and the
    deck name when `name` is given (so an existing deck is renamed to the prefixed
    name on the next --update). Non-fatal: warns and returns False on failure rather
    than aborting the upload.
    """
    body = {"private": bool(private), "unlisted": bool(unlisted)}
    if name:
        body["name"] = name
    status, data = _request(
        SETTINGS_URL.format(id=deck_id), method="PATCH", token=token, body=body,
    )
    if status in (200, 201):
        extra = f" name='{name}'" if name else ""
        log(f"  settings set: private={bool(private)} unlisted={bool(unlisted)}{extra}")
        return True
    log(f"  WARNING: could not set settings (HTTP {status}: {str(data)[:160]}); "
        "deck settings left unchanged")
    return False


# ---------------------------------------------------------------------------
# manifest (name -> deckRelationId) so we can update a deck in place later
# ---------------------------------------------------------------------------

def manifest_path(deck_path):
    return deck_path + MANIFEST_SUFFIX


def load_manifest(deck_path):
    p = manifest_path(deck_path)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def write_manifest(deck_path, deck_id, url, relations):
    with open(manifest_path(deck_path), "w", encoding="utf-8") as f:
        json.dump({"deckId": deck_id, "url": url, "relations": relations}, f, indent=1)


def update_deck(token, deck_path, resolved, dry_run=False, private=False, unlisted=True, name=None):
    """Update an existing deck IN PLACE using the manifest (no deck read needed).

    Diffs new resolved cards vs the stored name->{rid,qty} map: deletes the
    relations of removed/qty-changed cards and adds new/qty-changed cards, keeping
    the same deck id + URL. Returns the deck URL, or None if there is no usable
    manifest (caller should fall back to create). Raises RuntimeError on a hard
    failure mid-update (so the caller does NOT orphan the existing deck by creating
    a duplicate).
    """
    man = load_manifest(deck_path)
    if not man or not man.get("deckId"):
        log("  no manifest for --update; will create a fresh deck instead")
        return None
    deck_id = man["deckId"]
    relations = {k: dict(v) for k, v in (man.get("relations") or {}).items()}
    new = {r["name"]: r for r in resolved if r.get("name")}

    def changed(nm):
        return nm in relations and relations[nm].get("qty") != new[nm]["quantity"]

    to_remove = [(nm, relations[nm]["rid"]) for nm in relations
                 if nm not in new or changed(nm)]
    to_add = [new[nm] for nm in new if nm not in relations or changed(nm)]
    log(f"  update {deck_id}: remove {len(to_remove)}, add {len(to_add)}, "
        f"keep {len(relations) - len(to_remove)}")
    if dry_run:
        log("  (dry-run: no changes applied)")
        log(f"    - remove: {[nm for nm, _ in to_remove][:12]}")
        log(f"    + add:    {[r['name'] for r in to_add][:12]}")
        return man.get("url") or f"{BASE}/decks/{deck_id}"

    failed = 0
    for nm, rid in to_remove:
        if delete_relation(token, rid):
            relations.pop(nm, None)
        else:
            failed += 1
            log(f"  WARN: delete failed for '{nm}' (relation {rid})")
    if to_add:
        newrel = add_cards(token, deck_id, to_add)
        if newrel is None:
            # Some relations may already have been deleted above; persist what we know
            # so the manifest stays consistent with the deck, then signal hard failure.
            write_manifest(deck_path, deck_id, man.get("url") or f"{BASE}/decks/{deck_id}", relations)
            raise RuntimeError(
                f"adding {len(to_add)} card(s) to deck {deck_id} failed during in-place update")
        relations.update(newrel)
    # Re-assert visibility + name so a re-uploaded deck keeps the intended setting
    # (visibility defaults to unlisted; name carries the AI- prefix). Non-fatal.
    set_deck_settings(token, deck_id, private, unlisted, name=name)
    url = man.get("url") or f"{BASE}/decks/{deck_id}"
    write_manifest(deck_path, deck_id, url, relations)
    if failed:
        log(f"  update finished with {failed} failed delete(s) — deck may have stale cards")
    return url


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Upload a deck.txt to Archidekt")
    ap.add_argument("--deck", default="deck.txt", help="path to deck.txt (default: deck.txt)")
    ap.add_argument("--name", help="deck name (default: commander name from deck.txt)")
    ap.add_argument("--name-prefix", default="AI-",
                    help="prefix prepended to the deck name to mark it AI-built "
                         "(default: 'AI-'; pass --name-prefix '' to disable). "
                         "Skipped if the name already starts with it.")
    ap.add_argument("--format", default="edh", help="edh|commander|custom|standard (default: edh)")
    ap.add_argument("--bracket", type=int, default=None, help="EDH bracket 1-5 (optional)")
    ap.add_argument("--private", action="store_true",
                    help="make the deck private (NOTE: CommanderSalt cannot score private decks)")
    ap.add_argument("--unlisted", action="store_true",
                    help="make the deck unlisted (this is the default)")
    ap.add_argument("--public", action="store_true",
                    help="make the deck fully public/listed (override the unlisted default)")
    ap.add_argument("--update", action="store_true",
                    help="update the existing deck in place using the manifest "
                         "(<deck>.archidekt.json) instead of creating a new deck; "
                         "falls back to create if no manifest exists")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse + validate (and, with --update, show the diff plan); no writes")
    args = ap.parse_args()

    if not os.path.exists(args.deck):
        log(f"deck file not found: {args.deck}")
        return 2
    try:
        deck_text, n = read_deck(args.deck)
    except ValueError as e:
        log(str(e))
        return 2
    name = args.name or derive_name(deck_text)
    # Mark AI-built decks with a tunable prefix (default "AI-"); avoid double-prefixing.
    prefix = args.name_prefix or ""
    if prefix and not name.startswith(prefix):
        name = prefix + name
    mode = "update" if args.update else "create"

    # Visibility: default is UNLISTED (accessible by direct link, not listed in
    # search/profile). CommanderSalt CAN score unlisted decks (it fetches by URL);
    # only --private blocks scoring. --public opts back into a fully listed deck.
    private = bool(args.private)
    if args.public:
        unlisted = False
    elif args.unlisted:
        unlisted = True
    else:
        unlisted = not private  # default: unlisted unless private was requested
    if private:
        log("  NOTE: --private set; CommanderSalt will not be able to score this deck")

    log(f"deck: {args.deck} ({n} card lines) -> name '{name}' [mode: {mode}] "
        f"(private={private}, unlisted={unlisted})")

    if args.dry_run and not args.update:
        log("dry-run: deck.txt parsed OK, no upload performed")
        return 0

    email = os.environ.get("ARCHIDEKT_EMAIL")
    password = os.environ.get("ARCHIDEKT_PASSWORD")
    if not email or not password:
        log("missing ARCHIDEKT_EMAIL / ARCHIDEKT_PASSWORD in environment")
        return 3

    log("logging in...")
    token = login(email, password)
    if not token:
        return 4

    log("resolving cards (server-side parse)...")
    parse_resp = resolve_cards(token, deck_text)
    if parse_resp is None:
        log("card resolution failed")
        return 6
    resolved = _iter_resolved(parse_resp)
    log(f"resolved {len(resolved)} card entries")
    if not resolved:
        log("could not extract resolved cards from massDeckEdit response; "
            "keys: " + ", ".join(parse_resp.keys()))
        return 6

    # --- update existing deck in place (manifest-backed diff) ---
    if args.update:
        try:
            url = update_deck(token, args.deck, resolved, dry_run=args.dry_run,
                              private=private, unlisted=unlisted, name=name)
        except RuntimeError as e:
            # Hard failure mid-update: leave the existing deck in place rather than
            # creating a duplicate. Caller falls back to manual import.
            log(f"in-place update failed: {e}; existing deck left as-is (no duplicate created)")
            return 6
        if url is not None:
            log("done." if not args.dry_run else "dry-run done.")
            print(url)
            return 0
        log("no manifest — falling back to create a new deck")
        if args.dry_run:
            return 0

    # --- create a fresh deck ---
    deck_format = FORMATS.get(args.format.lower(), FORMAT_EDH)
    log("creating deck...")
    deck_id = create_deck(token, name, deck_format, args.bracket, private, unlisted)
    if not deck_id:
        return 5
    url = f"{BASE}/decks/{deck_id}"
    log(f"created empty deck: {url}")

    log("saving cards...")
    relations = add_cards(token, deck_id, resolved)
    if relations is None:
        log(f"save failed; deck at {url} may be empty/partial")
        return 6
    write_manifest(args.deck, deck_id, url, relations)
    log(f"  wrote manifest {manifest_path(args.deck)} ({len(relations)} relations) for future --update")

    log("done.")
    print(url)  # stdout: the final deck URL, for the skill to surface
    return 0


if __name__ == "__main__":
    sys.exit(main())
