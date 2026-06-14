# The Remote-Oracle (CommanderSalt)

This skill scores power with **two oracles** and is governed by the **lower** of the two:

- **local-oracle** — the `references/oracle.md` rubric. Fast, runs every iteration, but biased (it has historically over-rated decks). Estimate only.
- **remote-oracle** — **CommanderSalt** (`commandersalt.com`), a data-backed power number derived from each card's EDHREC salt score + combos + bracket + synergy, compressed to a 0–10. Authoritative, but the deck must be hosted + ingested to read it.

## The governing rule (min of the two)

```
current_power = min(local_oracle_power, remote_oracle_power)
```

The deck has met `target_power` ONLY when **both** oracles are ≥ target. Always revise toward whichever is **lower**:
- **local 8.1, remote 6.0 → current = 6.0.** The deck is actually weak by the data; the local-oracle inflated. Raise *real* power (see "What CommanderSalt rewards") AND tighten the local components that over-scored. Do NOT declare success.
- **remote 8.0, local 6.0 → current = 6.0.** Keep improving the dimension the local-oracle says is weak; the min still governs, so converge only when both clear the target.
- Never report `current_power` above the lower oracle. Never substitute an *estimate* for a real remote reading at the convergence gate.

## What CommanderSalt actually rewards (why combos alone didn't move it)

CommanderSalt's power number is dominated by **EDHREC salt-score density + bracket + combo count + synergy** — i.e. *how many individually powerful / format-warping / "salty" staples the deck runs*, not whether it merely contains an infinite. Adding three infinite combos barely moved a value deck (6.17 → 6.2) because the supporting cards were low-salt. To raise the **remote** number, increase the density of high-impact staples the data rewards, within the bracket:
- **Fast mana & rocks** (Sol Ring, Mana Crypt*, signets, Jeweled Lotus*) — *=Game Changers, mind the 3-cap.
- **High-salt staples / Game Changers** the format hates (Cyclonic Rift, Rhystic Study, Smothering Tithe, The One Ring, premium tutors) — spend the full bracket GC budget on these.
- **Premium interaction & efficient tutors**, low average mana value (a fast, lean curve), and **proven combos that use salty pieces**.
- Use the public card dataset `GET https://api.commandersalt.com/meta` (per-card `categories` like `fastmana` + `metaShare`) to identify which candidate cards score high.
A grind/value pile of low-salt cards caps ~6 on CommanderSalt no matter how synergistic — the remote-oracle measures *staple/salt density*, so build for that to push the number up.

## How to obtain the remote number — FULLY AUTOMATED (no human paste, no login)

Backend host: `https://api.commandersalt.com` (the `commandersalt.com/api/*` paths are just the static SPA — do not use them). Anonymous scoring works; no login is required (the account-gated `/managedecks` endpoint is only for saving a deck to a profile — irrelevant here).

The pipeline (reverse-engineered from the SPA's `importDeckList`):
1. **Ingest:** `POST https://api.commandersalt.com/decks?url=<deckUrl>` → `{"id": <contentHash>, …}`. Accepts Archidekt / Moxfield / TappedOut deck URLs. (Optional `&oldDeckId=<id>` to refresh a prior score.)
2. **Read / poll:** `GET https://api.commandersalt.com/decks?id=<contentHash>` → once `status.exists` is true, the fields are:
   - `powerLevelRating` — the **power number** (e.g. `9.02`); `powerLevelDisplayValue` is its rounded display form.
   - `saltRating`, `comboRating`, `threatRating`, `archetypeLabel`, `colorIdentity`, `_cardCount`.

### The loop: create ONCE, then UPDATE-IN-PLACE + requery (no clutter, no paste, no login)
```
# First checkpoint — create the deck (also writes <deck>.archidekt.json manifest):
python3 scripts/upload_to_archidekt.py --deck deck.txt --name "<name>" --format edh --bracket <N>
#   -> stable deck URL, e.g. https://archidekt.com/decks/<archidektId>

# Every later checkpoint — UPDATE the SAME deck in place (diff from the manifest):
python3 scripts/upload_to_archidekt.py --deck deck.txt --update          # (--dry-run to preview the +/- plan)

# Score it (same URL every time):
python3 scripts/query_commandersalt.py --archidekt-id <archidektId> [--json]
```
`upload_to_archidekt.py --update` reads the manifest (`<deck>.archidekt.json`, a name→{relationId,qty} map captured from the create's `modifyCards` response), diffs it against the new `deck.txt`, then **DELETEs the relations of removed/changed cards** (`DELETE /api/decks/relations/<id>/`) and **adds new/changed cards** — keeping the **same deck id and URL**. No deck read-back is needed. It falls back to creating a fresh deck if no manifest exists.

`query_commandersalt.py` POST-ingests + polls and prints `power=<n> | salt=… combo=… threat=… | archetype=… | <ci> <count> cards | <commandersalt url>` to stderr and the bare number to stdout (`--json` adds `commandersaltId` + sub-ratings). Exit codes: 0 ok · 2 bad usage · 4 ingest failed · 5 score timed out.

### Why this avoids clutter on BOTH sides
- **Archidekt:** `--update` mutates one deck in place → one stable URL across the whole loop (never a pile of draft decks).
- **CommanderSalt:** because the Archidekt URL is stable, re-querying re-fetches the *same* URL and returns the **same CommanderSalt id**, refreshed with the new score (verified: editing the deck moved its `threatRating` under the same csid). So you get an in-place refresh for free — no need for the authenticated `oldDeckId` route.
- The deck **must be public** (not `--private/--unlisted`) or CommanderSalt can't fetch it ("Deck URL invalid, or deck is not publicly visible"). The upload script creates public decks by default.

### `--old-deck-id` (optional, legacy)
`query_commandersalt.py --old-deck-id <prev_csid>` appends `&oldDeckId=` (the SPA's explicit refresh). That route is **authenticated-only** — anonymous calls 404 — so the script transparently falls back to a plain ingest. With the update-in-place loop above the URL is already stable, so this flag is rarely needed; keep it only as a belt-and-suspenders option.

### Loop method
1. Run the **local-oracle every iteration** (cheap, no network).
2. At each **checkpoint** (whenever the local-oracle thinks the target is met, and always before declaring convergence): upload → query CommanderSalt with the script → that's the **real remote reading** (never estimated).
3. `current_power = min(local, remote)`; loop until **both** ≥ `target_power` and the bracket checklist passes. Revise toward whichever is lower (the data finding: CommanderSalt is moved by fast/lean cEDH-grade composition — top-metaShare staples, efficient manabase, fast mana, combos — not by synergy or raw staple-count alone).
4. Between checkpoints you MAY carry a calibration offset (`last_remote − last_local`) to plan, but the convergence gate needs a fresh script run.
5. **Fallback only if the API breaks:** if `query_commandersalt.py` exits non-zero (CommanderSalt changed its endpoints — re-derive from the SPA's `importDeckList`), then and only then ask the user to paste the number. Otherwise never ask.
