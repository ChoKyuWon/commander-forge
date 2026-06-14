# Deckbuilding Logic (ported from deck-forge)

Concepts and gates adapted from the `deck-forge` skill (dan-blanchard/mtg-skills) into
this non-interactive, deck.txt-emitting pipeline. deck-forge is a live collaborative
browser tool; its UI/hub/Python machinery does not apply here, but its **reasoning
logic** does. The Builder, Oracle, and Critic all defer to the rules below.

---

## 1. The Iron Rule (contract #1 — NEVER relaxed)

**NEVER name a card from memory, and NEVER assert what a card does from assumption.**
You propose *patterns, searches, and judgments*; a real lookup names the card and supplies
its oracle text.

- Every card you add, score, or endorse MUST be grounded in a real Scryfall result
  (`https://api.scryfall.com/cards/named?exact=...` or the `/cards/collection` batch
  endpoint), not recalled from training data.
- **Before asserting a synergy, read the card's actual oracle text and quote the clause
  that justifies it.** Training data is not oracle text. *Tinybones, the Pickpocket*
  steals from **opponents'** graveyards — so it does NOT want self-mill. Scope matters.
- If you can't express a hunch as a search/lookup, that is a prompt to widen the search,
  not to invent a card.
- This rule is why this pipeline already verifies color identity and Game Changers against
  Scryfall in `SKILL.md §7`. The lesson is general: **memory is for patterns, the API is
  for facts.** A card named from memory (wrong color, wrong text, doesn't exist) is the
  single most common failure mode — the Iron Rule exists to kill it.

Practical contract for this skill:
- The Builder names candidate cards, then **confirms each via Scryfall** (exact name,
  color identity, type line, mana value, current Oracle text, Commander legality) before
  committing them to the list.
- The Oracle, when crediting any specific interaction/combo/MV-dependent score, verifies
  the fact first (per `oracle.md`'s "verify before crediting" rule).

---

## 2. Signal (clause-scoped synergy fact)

A **Signal** is a precisely-scoped fact extracted from ONE card's oracle text — a trigger
("a creature you control enters"), a payoff, a type-matters hook, or a cost reducer. The
**scope is part of the signal's identity**: read the commander's (and each card's) oracle
literally.

- Sharpen vague "themes" into clause-scoped signals. "Graveyard matters" is too loose;
  "exile cards from an **opponent's** graveyard during your turn" is a signal.
- Author synergy searches around the **precise phrase**, not loosely-related subtypes. A
  Plant/Dryad *creature* token is not a *land* creature; when a synergy depends on a
  card's TYPE, scope the search by type line too (e.g. `t:land becomes a … creature`),
  because "becomes a … creature" alone also matches clones and artifact-animation.
- The Research Dossier should record the commander's signals (with the quoted clause), and
  the Builder should map each Engine card back to a signal it serves.

---

## 3. Card roles: Spine / Engine / Filler

Classify every nonland card into exactly one role. This taxonomy drives composition
(Builder), the synergy denominator (Oracle), and cut selection (Critic).

- **Spine** — mandatory scaffolding every deck needs regardless of plan. Hard-counted
  against the template: **ramp, card draw, interaction (counterspells fold into
  interaction — not a separate role), board wipes**, plus the mana base. Conditional spine
  (advisory, scaled by Shape): **win conditions, protection**. Spine health is measured by
  *template deviation*, NOT by theme focus — a deck is never "too unfocused" for running
  its removal.
- **Engine card** — a nonland card whose primary job is to serve one of the commander's
  signal-derived directions (payoffs, enablers, synergy pieces). Engine cards are the ONLY
  pool the focus metric (§5) measures. A Spine card may *also* serve a signal (a
  dual-purpose "win-win"); that only ever *adds* to focus, never subtracts.
- **Filler** — a nonland card that is neither Spine nor serves any direction: "good stuff
  that does nothing *here*." Filler may be individually strong; it is just unsupported in
  this deck. **A high filler share is a spread/efficiency problem and the first place cut
  selection looks.** Aim to drive filler toward zero in a focused Commander deck.

Generic colorless/fixing staples (Sol Ring, signets, basic fixing) count as Spine, not
Engine, and are excluded from the focus/synergy denominator.

---

## 4. Shape (the speed / role axis)

Infer the deck's **Shape** — aggro / midrange / control / combo — deterministically from
its composition (curve, creature density, interaction density, combo presence). One deck
has exactly one Shape (orthogonal to its synergy directions, of which it can have several).

Shape scales the **conditional Spine floors and curve expectations**:
- *aggro* — lowest curve, more early plays, fewer board wipes (it doesn't want to wipe its
  own board), more reach/closing power.
- *midrange* — balanced curve, standard interaction, clear top-end win conditions.
- *control* — more interaction + card draw, higher land count, fewer but harder-to-answer
  win conditions; reads `SPINE-LED`, never "spread thin," because the Spine *is* the plan.
- *combo* — protection + tutors + the combo pieces; curve serves the assembly, not the
  board.

Bracket (power level) is a DIFFERENT axis from Shape — do not conflate them.

---

## 5. Focus (the anti-"spread too thin" metric)

Measure concentration of **Engine cards** across the commander's signal-derived directions
(Spine-role directions and lands excluded — scaffolding must not masquerade as the theme).
Score each direction on a **tiered per-100 floor**:

- **Main** theme — at/above ~20 cards per 100.
- **Sub** theme — at/above ~10 per 100 (genuinely shallower than a main, so it is NOT held
  to the main's bar).
- **Emerging** theme — at/above ~5 per 100 (a real but under-committed direction → "commit
  more or cut," not noise).

The research ideal is **one main + one sub**. **3+ main-depth themes reads `SPREAD-THIN`**
— a Critic `[theme]` defect. Near-duplicate directions (≥80% shared cards) collapse to one
so a theme isn't double-counted. Shape-aware: a small-engine control deck is `SPINE-LED`,
not spread-thin. This is concentration, not a quality score.

---

## 6. Efficiency (curve / tempo health, Shape-aware)

A multi-readout (not one opaque number) feeding the Oracle's **Mana Efficiency** component:
- average mana value *within the Shape's expected band*,
- ramp adequacy for that curve (enough acceleration, not so much it floods),
- early-play front-load (do you have turn 1–3 plays?),
- **closing power** — enough top-end to actually win, not so much it clogs.

This is about the *nonland* curve; land count/color is the separate Curve gate (§7). There
is no per-card "card quality / rate" judgment — this skill scores structure, not vibes.

---

## 7. Hard gates: land Curve gate + Flood line

Distinguish **hard gates** (block a finished deck) from **soft templates** (nudges only).

- **Curve gate (HARD).** The mana base has a land *floor*. For Commander, a practical
  reference floor is **~Karsten's guidance: roughly 33–34 lands minimum, +1 for every ~1.0
  the deck's average mana value sits above ~2.5–3.0**, adjusted DOWN only for genuine extra
  mana sources (cheap ramp, MDFC land-backs counted at ~½, cantrips). Below the computed
  floor the deck is a **FAIL** and may not be finalized without an explicit, acknowledged
  override that cites the compensating evidence (low avg MV + high cheap-card-advantage
  count). This is the hard analog of the soft 35–37 land suggestion in `builder.md`.
- **Flood line (SOFT).** The upper band is `recommended_lands + 2`, where `recommended_lands`
  is the **soft 35–37 suggestion** for this deck (the `builder.md` band tuned for its curve),
  **not** the hard Karsten floor — so the flood line sits around 37–39, not floor+2. Above it
  the deck is over-landed → a soft FLOOD nudge to trim basics (most over-produced color first)
  down to recommended. It **never blocks** — an all-lands/few-pieces combo deck is legitimate.
- **Role-count templates are SOFT.** The ramp/draw/interaction/payoff bands are nudges
  (template deviation = distance outside the band), never gates. Only the land Curve gate,
  identity, singleton, count, and bracket checklist are hard.

---

## 8. Combo as a secondary layer (Commander Spellbook)

A **Combo** is a *closed* interaction that produces unbounded value or wins the game —
distinct from an ordinary **Synergy package** (cards that amplify a shared signal but do
not, by themselves, end the game). Do not call a normal synergy a combo.

**Combos are the primary lever for high power within a bracket — not just a hazard to avoid.**
The difference between a CommanderSalt-6 and a CommanderSalt-8 *Bracket-3* deck is whether it
has a **compact, repeatable, protected kill**. A combo is how you get one without leaving the
bracket. So combo detection runs in BOTH directions:

- **As a power-builder (when `target_power` is high):** find a real combo for the
  commander's colors/strategy on **Commander Spellbook** (`commanderspellbook.com`), verify
  each piece's oracle text (Iron Rule), and build around it with redundancy + tutors + fast
  mana + protection (see `references/builder.md` → "Building for high power within a
  bracket"). A **Bracket-3-legal** combo is one that assembles **mid-game (~turn 6+, not
  reliably earlier)**, stays within the **3-Game-Changer cap**, and uses no MLD / extra-turn
  chains. Example pattern (illustrative — verify each piece's oracle text on Commander
  Spellbook and the score on CommanderSalt before relying on it; never treat this card fact or
  number as ground truth from memory): Aggravated Assault + an equipment/mana source = infinite
  combat, which needs ~8 mana + a connecting creature → comes online ~turn 6–8 → legal in
  Bracket 3 and worth ~8 on CommanderSalt.
- **As a bracket guard (always, in §7):** cross-check the deck's pairs against Commander
  Spellbook. If a compact 2-card game-ending/lockout/infinite reliably assembles **before
  ~turn 6**, the deck is **Bracket 4+**, not 3 — slow it (cut a tutor/fast-mana enabler) or
  accept the higher bracket. `find-my-combos` also reports near-misses (one piece away);
  those don't change the current bracket but show how combo-adjacent the deck is.
- When intentionally *excluding* a combo to stay in-bracket (e.g. omitting Exquisite Blood
  so Vito is not an infinite), record it explicitly in the log's Risks so it isn't
  re-added.

---

## 9. No-listing card is never free

When a `budget` ceiling is set: a card for which neither bulk data nor the live price API
returns a price is **likely scarce/expensive — treat it as costly, never as $0.** Do not
let a missing price sneak an expensive card under a budget. Surface "price unknown — assume
expensive" rather than counting it as free.
