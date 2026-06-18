# Auto-upload to Archidekt

This skill can push the finished `deck.txt` straight to the user's Archidekt
account via `scripts/upload_to_archidekt.py`. Archidekt has **no official,
documented write API** — the script uses the same private endpoints Archidekt's
own web app calls. They can change without notice; this file documents how they
work and how to repair them.

## Credentials (required)

The script authenticates with the user's Archidekt login, read from the
environment — never hardcode or commit these:

```
ARCHIDEKT_EMAIL=you@example.com
ARCHIDEKT_PASSWORD=••••••••
```

Set them in the shell (e.g. `export` in `~/.zshrc`) or in Claude Code's
`settings.json` `env` block. If either is missing the script exits **3** and the
skill falls back to manual import.

## How to run it

From the directory that contains `deck.txt`:

```
python3 scripts/upload_to_archidekt.py \
    --deck deck.txt \
    --name "<deck name>" \
    --format edh \
    --bracket <1-5>      # optional
    [--name-prefix "AI-"] [--public] [--unlisted] [--private]
```

- `--name` defaults to the card on the `[Commander]` line.
- `--format` defaults to `edh` (Commander); other values: `commander`, `custom`, `standard`.
- `--bracket` is optional and only applied for EDH.

### Deck name prefix (default: `AI-`)

AI-built decks are marked with a tunable name prefix so they're easy to spot in the
user's Archidekt account. The final deck name is `<prefix><name>` (e.g.
`AI-Phlage, Titan of Fire's Fury`).

- **`--name-prefix`** defaults to **`AI-`**. Pass a different string to change it, or
  `--name-prefix ""` to disable the prefix entirely.
- The prefix is **idempotent** — it is skipped if the name already starts with it, so
  repeated `--update` runs never stack `AI-AI-…`.
- On `--update`, the (prefixed) name is re-asserted via `PATCH /api/decks/<id>/update/`,
  so an existing deck is **renamed** to the prefixed name on its next update.

### Visibility (default: UNLISTED)

Uploaded decks default to **unlisted** — accessible by direct link but not shown in
search or on the user's public profile. This is the right default for decks the skill
generates on the user's account.

- **`--unlisted`** (default) — accessible by URL, not listed. **CommanderSalt CAN score
  unlisted decks** (it fetches the deck by its direct URL), so the remote-oracle loop works
  normally — no need to make decks fully public for scoring.
- **`--public`** — fully listed/public (opt out of the unlisted default).
- **`--private`** — only the owner can see it. **CommanderSalt CANNOT score private decks**
  (it can't fetch them), so do not use `--private` if you still need a remote-oracle reading.

On `--update`, the script re-asserts the resolved visibility via
`PATCH /api/decks/<id>/update/`, so a deck stays unlisted across the whole optimization
loop (and flips an older public deck to unlisted on the next update).
- `--dry-run` (create mode) parses/validates `deck.txt` and makes **no** network
  calls — use it to confirm formatting before a real upload.
- `--dry-run --update` still **logs in and resolves the cards** over the network
  (it must, to compute the add/remove diff against the manifest), but performs
  **no writes** — it only prints the `+`/`−` plan. So "dry-run" means "no
  mutations," not "no network," in update mode.
- Stdlib only (`urllib`); nothing to install.

On success the **last stdout line is the deck URL** (`https://archidekt.com/decks/<id>`);
all progress goes to stderr. Exit code `0` = success.

### Exit codes
| code | meaning | skill action |
|------|---------|--------------|
| 0 | deck created + cards saved | report the URL |
| 2 | bad usage / unreadable deck.txt | fix input |
| 3 | missing credentials | tell user to set env vars, fall back to manual import |
| 4 | login failed | report, fall back to manual import |
| 5 | deck create failed | report, fall back to manual import |
| 6 | card resolve/save failed (deck may be empty/partial) | give the URL + tell user to import deck.txt manually |

**Any non-zero exit → fall back to manual import.** Never treat a failed upload
as a failed build; `deck.txt` is always written first (see SKILL.md §6).

## The pipeline (reverse-engineered from Archidekt's frontend)

All write calls send header `Authorization: JWT <token>`.

1. **Login** — `POST /api/rest-auth/login/`
   body `{"email","password"}` → `{"token","refresh_token","user":{...}}`.
   The access token is the `token` field (dj-rest-auth).

2. **Create deck** — `POST /api/decks/v2/`
   ```json
   {"name","deckFormat":3,"edhBracket":<int|null>,"description":"","featured":"",
    "playmat":"","private":false,"unlisted":true,"theorycrafted":false,
    "game":null,"cardPackage":null,
    "extras":{"decksToInclude":[],"commandersToAdd":[],
              "forceCardsToSingleton":false,"ignoreCardsOutOfCommanderIdentity":true}}
   ```
   `deckFormat` 3 = EDH/Commander. Returns the deck object incl. `id`.

3. **Resolve cards** — `POST /api/cards/massDeckEdit/`
   body `{"parser":"archidekt","current":"","edit":"<deck.txt contents>"}`.
   Archidekt parses the **Archidekt text format** server-side (the exact format
   `deck.txt` uses, including `[Category]` tags and `[Commander]`), resolving
   each name to an Archidekt card id. Returns `syntaxErrors`, `cardErrors`, and
   the resolved cards (`toAdd` / `categories`). The script warns on any
   `cardErrors` (names Archidekt couldn't match).

4. **Persist** — `PATCH /api/decks/<id>/modifyCards/v2/`
   ```json
   {"cards":[{"action":"add","cardid":<id>,"customCardId":null,
              "categories":["Ramp"],"patchId":"0",
              "modifications":{"quantity":1,"modifier":"Normal","customCmc":null,
                               "companion":false,"flippedDefault":false,
                               "label":",#656565"}}]}
   ```

The commander is handled by the `[Commander]` category tag in `deck.txt` — the
parser places it in Archidekt's Commander zone; no separate commander step needed.

5. **Set settings (on `--update`)** — `PATCH /api/decks/<id>/update/`
   body `{"private":false,"unlisted":true,"name":"AI-<deck name>"}`. The plain
   `/api/decks/<id>/` route only allows `GET`/`DELETE`; deck settings (name, privacy) live
   on the `/update/` sub-route (`GET, PUT, PATCH, DELETE`). The create step (2) sets these
   inline, so this is only needed to keep an existing deck's visibility (unlisted) and name
   (the `AI-` prefix) in sync on re-upload. Handled by `set_deck_settings()`.

## If Archidekt changes the API

Symptoms: login still works but step 3 or 4 returns 4xx/5xx, or the deck is
created empty. To re-derive the endpoints:

1. Log into archidekt.com in a browser, open DevTools → Network.
2. Create a deck and paste a list via the deck builder's mass-edit box.
3. Watch for the calls to `/api/decks/v2/`, `/api/cards/massDeckEdit/`, and
   `/api/decks/<id>/modifyCards/v2/`. Compare request bodies to the shapes above
   and update `scripts/upload_to_archidekt.py` (`CREATE_URL`, `PARSE_URL`,
   `MODIFY_URL`, `SETTINGS_URL`, and the body builders). For the visibility PATCH,
   toggle a deck's privacy in the UI and watch for the `PATCH /api/decks/<id>/update/`
   call.

These endpoints were extracted from the Next.js bundle (`_app.js`,
module 7244 = deck service, module 15117 = save service, `massDeckEdit` in the
deck-builder chunk). The frontend resolves names with the `"archidekt"` parser,
so the script never has to do card-id lookups itself.
