# Research Protocol (read fully before building)

You are gathering evidence to ground every deckbuilding decision. Vibes are not evidence. The output of this phase is a **Research Dossier** that the Builder and Critic both consult.

**The Iron Rule governs research** (`references/deckbuilding-logic.md §1`): never record a card or a synergy from memory. Ground every card in a real Scryfall lookup, and before logging a synergy, read the card's actual oracle text and **quote the clause** that justifies it — training data is not oracle text. Extract the commander's **signals**: precisely-scoped facts from its oracle (scope is part of the signal — *Tinybones* steals from **opponents'** graveyards, which is a different signal from "graveyard matters"). The Dossier's directions should each trace to a quoted signal. Use **Commander Spellbook** for combos rather than recalling them.

## Mindset

Search **aggressively**. Assume your first impression of the commander is incomplete. Assume the obvious EDHREC list is the *average* deck, not the *optimized* one, and that optimized lists and competitive discussion will disagree with it in informative ways.

## Required sources (use several every time — never just one)

1. **EDHREC** — average inclusions, themes, synergy boxes, "high synergy" and "top cards" per theme. This is your baseline, not your conclusion.
2. **Moxfield** — search for the commander; open several **highly-viewed / highly-liked** lists, especially ones tagged optimized/competitive. Note where they diverge from EDHREC.
3. **Archidekt** — same, a second optimized-list reference; cross-check card choices and mana bases.
4. **Reddit** — r/EDH, r/CompetitiveEDH, and commander/archetype-specific threads. Capture *disagreements*, pet-card debates, "trap card" warnings, and meta calls.
5. **Articles / primers / guides** — strategy primers, set-review tech, "best cards for X" pieces, and any recent-set updates.
6. **Scryfall** — exact card names, color identity, Commander legality, and current Oracle text for any card where precision matters.
7. **Official bracket/Game Changer source** — the **canonical WotC source**: the official Commander page (`magic.wizards.com/en/formats/commander`) and the latest "Commander Brackets" announcement article (search "Wizards Commander Brackets Game Changers" for the most recent update — the list is revised periodically). Pull the Game Changers list and bracket rules from there, not from memory or local examples (which are illustrative only and go stale). Record the source URL and date you checked in the dossier.

## Search loop with gates

Do at least 2–3 passes. After each pass, answer honestly:

- Do I have enough evidence to commit to a shell?
- Am I leaning only on EDHREC? (If yes → pull Moxfield/Archidekt/Reddit.)
- Do Reddit discussions disagree with the aggregator data? (If yes → document both sides.)
- Do optimized Moxfield/Archidekt lists differ from the EDHREC average? (If yes → understand *why*.)
- Am I missing recent tech (new sets, recently-spiked cards, reprints, errata, ban-list changes)?

If any answer reveals a gap → **SEARCH AGAIN**. Do not stop early.

## Stopping criterion

Stop only when **either**:
- **≥3 independent sources agree** on the core shell and key synergy pieces, **or**
- the remaining disagreements are **explicitly documented** (what's disputed, who argues which side, and your provisional call + why).

## Tactics

- Run multiple web searches in parallel; fetch the most promising pages.
- For aggregator pages that are JS-heavy or paywalled, search for the same info via Reddit/article mirrors.
- You MAY spawn an `Explore` or `general-purpose` subagent to fan out searches, but YOU consolidate the dossier.
- Record card names precisely; verify color identity and current legality/printing for anything you're unsure about.

## Research Dossier (the deliverable)

Produce and keep in working memory:

- **Commander signals:** the commander's clause-scoped signals quoted from its oracle text (trigger / payoff / type-matters / cost-reducer), each with the exact phrase. These are the directions the Builder's Engine cards must serve.
- **Commander analysis:** rules text, what it actually rewards, common archetypes, power ceiling.
- **Staples by role:** ramp, draw, interaction, tutors, win conditions — with source agreement noted.
- **Theme tech:** cards that specifically enable the requested themes.
- **Recent tech:** anything from new sets / recent meta not yet reflected in stale aggregator data.
- **Documented disagreements:** the explicit list of disputes and your provisional resolution.
- **Bracket signals:** current Game Changers, mass land denial, extra-turn chains, early compact combos/lockouts, and any other construction-rule issues relevant to `target_bracket`.

Use this table for contested or non-obvious inclusions/cuts:

| Card | Role | Sources supporting | Sources disputing | Include/cut call | Reason |
|------|------|--------------------|-------------------|------------------|--------|

The table does not need to contain every staple, but it must cover cards that are expensive, narrow, bracket-sensitive, disputed by sources, or central to a win condition.

The Dossier is summarized into `optimization-log.md` at the end (never into `deck.txt`, which is pure importable card lines). Cite sources where it matters (especially for contested calls).
