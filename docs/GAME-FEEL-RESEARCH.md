# Making SyllabusSlayer *feel* like a game — research + plan

> **Scope (chosen with the user):** roguelike **progression & depth** is the priority · willing to **add a canvas battle layer (Phaser/PixiJS)** · want **both OSS repos and design patterns**.
>
> **Provenance:** from a deep-research run (6 angles, 22 sources, 105 claims → 25 surfaced with citations). The adversarial-verification pass was cut off by a usage limit, so the harness marked claims "unverified" — I've since cross-checked each against known facts (standard Slay-the-Spire mechanics + real repos/licenses) and flag the two license caveats that matter. Sources are listed at the end.

## The core diagnosis
Today's combat = a styled quiz + HP bar + damage numbers. What turns "quiz with HP" into "a roguelike" is three things, in priority order:
1. **A run map** — the single biggest lever. A branching path of choices (which fight? rest or risk an elite? grab treasure?) is what makes it a *run*.
2. **Relics that change how you play** + **reward choices** after fights — build variety and agency.
3. **Meta-progression + permadeath** — stakes and a reason to replay.
Then **canvas juice** (Phaser/Pixi arena) makes each hit *feel* good. Do the structure first, the juice second — a juicy quiz is still a quiz.

---

## A. Open-source repos / libraries / assets to adopt

| Project | License | Borrow | Notes |
|---|---|---|---|
| **yurkth/stsmapgen** | **MIT** ✅ | The **run-map generation algorithm** (Poisson-disk sample → Delaunay → A* start→boss → prune → repeat for branches). Port to TS. | Cleanest reusable map algo. (Only oddity: license bars using output to sell NFTs — irrelevant.) |
| **silverua/slay-the-spire-map-in-unity** | **MIT** ✅ | Map *design* reference — `MapConfig` idea, `extraPaths`, guaranteed start/pre-boss node counts, layer structure. | C#/Unity, so **pattern not code** — reimplement the layout rules in TS. |
| **phaserjs/template-nextjs** | **MIT** ✅ | **The canvas integration** — Phaser 4 + Next.js + a React↔Phaser **EventBus** bridge; `phaserRef` to reach the live game/scene. | Closest to our stack. Basis for the battle-arena layer. |
| **phaserjs/template-react** | **MIT** ✅ | Same EventBus + `forwardRef` bridge (Phaser 4 + React 19) if we prefer a non-Next harness for the game package. | Alternative to the above. |
| **@pixi/react v8** | **MIT** ✅ | Declarative Pixi in JSX (`<pixiSprite>` etc.) — lighter option if we only want VFX, not a full scene. | **Requires React 19** (we're on it). |
| **oskarrough/slaytheweb** | ⚠️ **AGPL-3.0** | **Study only** — its clean split of *engine* (cards/powers/monsters/map) from *UI* is the architecture to imitate. | AGPL is network-copyleft → **do not copy code** into this repo; learn the structure and rebuild. |
| **nicklemmon/react-deckbuilder** | ⚠️ **no license** (all-rights-reserved) | **Study only** — React + **XState** + TS turn-based card combat (no engine) — validates a state-machine combat approach. | No LICENSE file → legally can't reuse code; read for ideas. |
| **Kenney.nl** assets | **CC0** ✅ | Sprites, UI, particles, SFX packs — zero-attribution, commercial-ok. Fastest path to "looks like a game." | The go-to free asset source. |
| **game-icons.net** | **CC-BY 3.0** | 4000+ RPG icons (relics, abilities, enemies) — attribution required. | Perfect for relic/ability icons. |
| **OpenGameArt (LPC set)** | mixed (CC-BY-SA / GPL) | Character/monster sprite sheets — **check per-asset license**. | Use carefully; CC0 packs are safer. |
| **itch.io CC0 game-assets** | **CC0** ✅ | Backgrounds, enemy art, tilesets. | Filter by CC0. |
| **Freesound** | mixed (CC0 / CC-BY) | Hit/heal/UI SFX + ambience — filter to CC0. | Pair with **howler.js** (MIT) for playback. |
| **howler.js** · **tsParticles** · **Motion** · **GSAP** | MIT | Sound (howler), particle bursts (tsParticles), springs/tweens (Motion/GSAP) for juice. | Motion is already in the app. |

**Bottom line on repos:** the two MIT wins to *reuse* are **stsmapgen** (map algorithm) and the **phaserjs Next.js template** (canvas bridge). Slay-the-Web and react-deckbuilder are architecture references only (license-blocked). Assets: lean on **Kenney (CC0)** + **game-icons.net (CC-BY)**.

---

## B. Roguelike progression → mapped onto our schema

Our current game JSON is `Campaign → Acts → Encounters(minion/elite/boss) → Questions` + `CombatConfig`. Extensions (all backend-computed / generation-assisted, keeping the "LLM writes pedagogy, backend owns balance" split):

### B1. Run map (per act) — *do this first*
Add a **map** to each act: a layered DAG of **nodes** + **edges**. Node types:
- `battle` → an existing Encounter (minion/elite/boss). Boss node gates the act.
- `rest` → heal a % of HP **or** upgrade a relic (a choice).
- `event` → a risky text choice (small quiz gamble: answer a bonus Q for a reward, or skip).
- `treasure` → free relic.
- `shop` → spend run currency on relics / heals / "remove a hard question type".

Generation: the **LLM already produces encounters**; the **backend lays out the map deterministically** (stsmapgen-style or a simpler layered algorithm) and sprinkles rest/event/treasure/shop between battle layers. Slay-the-Spire's ratios are a good default (mostly battles, 1 rest before each boss, occasional elite/treasure).

**Schema add (proposed):**
```jsonc
// on each Act
"map": {
  "nodes": [{ "nodeId": "n1", "row": 0, "col": 2, "type": "battle",
              "encounterId": "enc_mito" | null, "kind": "minion|elite|boss" }],
  "edges": [{ "from": "n1", "to": "n5" }]
}
```
Player state gains `currentNodeId`; the client renders the map and lets the student pick the next reachable node. **This alone makes it a roguelike.**

### B2. Relics / power-ups (typed effects, not just numbers)
A **relic catalog** (authored once, JSON) with **typed effects** the server scoring already touches:
- `first_wrong_free` — first wrong answer per fight deals no HP damage.
- `streak_head_start` — streak multiplier starts one tier higher.
- `reveal_distractor` — on hard questions, one wrong option is greyed out.
- `overkill_heal` — excess damage on a kill heals you.
- `second_wind` — revive once at 25% HP (adds the permadeath tension release).

**Effects hook into `scoring.py`** (which is already server-authoritative): the run carries `ownedRelics`, and `score_answer`/HP logic consults them. Store on `PlaySession` (e.g. `relics JSON`, already have a `relics` column on `StudentProgress`). **The LLM may theme relic *names* to the topic; the backend owns the effect + magnitude** (same rule as combat tuning).

### B3. Reward choice after encounters
After a battle: **choose 1 of 3** (relic / heal / currency). After a boss: choose 1 of 3 **rarer** relics. This is a small client screen + a backend endpoint that applies the pick to the run. Mirrors Slay-the-Spire's boss/elite/chest reward tiers.

### B4. Meta-progression + permadeath
- **Permadeath:** HP → 0 ends the **run** (not the app). You keep meta-currency; you can restart the campaign (new map layout).
- **Currency + unlocks:** earn a soft currency per run; spend it to **unlock new relics / a starting perk / a cosmetic**. New table `student_meta` (or extend `StudentProgress`: `meta_currency`, `unlocked_relics JSON`).
- This turns "replay the course" into a progression loop — and gives the teacher dashboard richer signal (attempts across runs).

---

## C. Canvas battle layer (behind the React question UI)

**Recommendation: Phaser 4** as a lazily-loaded battle *scene* behind the React question card. React stays the source of truth + keeps the questions accessible (HTML); Phaser renders the *arena* (enemy sprite, player avatar, HP bars, attack/particle FX, screen-shake, floating damage). Bridge via the **EventBus pattern** from `phaserjs/template-nextjs`:
- React → Phaser: `EventBus.emit('answer-result', {correct, damage, streak})` → the scene plays the hit/particle/shake.
- Phaser → React: `EventBus.emit('attack-anim-done')` → React advances the turn.
- Mount client-only: `const BattleCanvas = dynamic(() => import('./BattleCanvas'), { ssr: false })` inside a `'use client'` wrapper (the pattern we already documented in the spec).

*(Lighter alternative: **@pixi/react v8** — declarative VFX only, React-19-native — if a full Phaser scene feels heavy. Phaser wins for batteries-included tweens/particles/audio/sprites.)*

## Game-feel techniques to implement on the canvas
From the juice literature ("Juice it or lose it" lineage): **anticipation → impact → follow-through** on every attack; **hit-stop** (freeze ~50–120ms on impact); **screen shake / camera punch** scaled to damage; **floating damage numbers** with easing + color (crit = streak); **particle bursts** on hit/heal; **squash-and-stretch** on the enemy sprite; **layered SFX** (swing + impact + crit ding) via howler. Keep it tasteful — juice amplifies feedback, it shouldn't obscure the question.

---

## D. Phased roadmap (a new milestone — call it M5: "make it a game")

| Phase | What | Effort | Why first |
|---|---|---|---|
| **M5.1 — Run map** | Map schema + deterministic generator (TS, stsmapgen-style) + a React map screen (pick your path); node types battle/rest/treasure to start. | Med | **Biggest feel jump.** Turns it into a run. No new art needed. |
| **M5.2 — Relics + reward choice** | Relic catalog + typed effects in `scoring.py` + "choose 1 of 3" after fights. | Med | Build variety + agency. |
| **M5.3 — Meta-progression + permadeath** | Run-end on HP 0, meta-currency, unlocks; extend `StudentProgress`. | Low–Med | Stakes + replay loop. |
| **M5.4 — Canvas arena + juice** | Phaser 4 battle scene via EventBus; enemy sprites (Kenney/CC0), hit-stop/shake/particles/SFX. | High | The visible "wow"; do after structure exists. |
| **M5.5 — Polish** | Music, transitions, event nodes, shop. | Low | Nice-to-have. |

**Order matters:** M5.1–M5.3 (structure) make it a roguelike on the *existing* React UI; M5.4 (canvas) makes it *look* like one. Ship in that order so each phase is demo-able.

---

## E. Learning-vs-luck guardrails (don't let it become a slot machine)
Backed by the reward-design research surfaced (context-related rewards beat generic ones for motivation *and* learning; luck-vs-skill framing changes engagement):
- **Correctness is never RNG.** Relics/luck adjust *combat consequences* (damage, HP, hints), never whether an answer is right. Knowledge always decides the fight.
- **Relics amplify good play**, they don't replace it (streak bonuses, wrong-answer cushions) — reward mastery, not luck.
- **Tie rewards to the content** where possible (a relic themed to the topic, a "mastery" bonus for a clean encounter) — the study found context-related rewards most effective for both motivation and learning.
- **Keep a floor:** even with bad luck, a student who knows the material should win; even with great relics, a student who doesn't shouldn't.

---

## Sources
Slay-the-Spire map: wiki (`slaythespire.wiki.gg/wiki/Map_Generation`), arXiv 2504.03918 · repos: github.com/yurkth/stsmapgen (MIT), github.com/silverua/slay-the-spire-map-in-unity (MIT), github.com/oskarrough/slaytheweb (AGPL-3.0), github.com/nicklemmon/react-deckbuilder (no license), github.com/phaserjs/template-nextjs (MIT), github.com/phaserjs/template-react (MIT) · canvas+React: pixijs.com/blog/pixi-react-v8-live, 3ee.com/blog/phaser-game-react-ui · juice: github.com/a327ex/blog/issues/47 · RNG/rewards: dl.acm.org/doi/10.1145/3491102.3517642, journals.sagepub.com/doi/10.1177/07356331261444108, medium.com fair-RNG-in-roguelikes · deck-building genre: en.wikipedia.org/wiki/Roguelike_deck-building_game · assets: kenney.nl/assets (CC0), game-icons.net (CC-BY 3.0), opengameart.org (LPC, mixed), itch.io/game-assets/assets-cc0 (CC0), freesound.org (CC0/CC-BY).

*(Adversarial verification did not run due to a usage-limit cutoff; claims cross-checked against known facts. Re-verify any license before shipping — esp. per-asset licenses on OpenGameArt/Freesound.)*
