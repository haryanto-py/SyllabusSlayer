"""Deterministic combat/RPG tuning (docs/BUILD-SPEC.md §4.2).

The LLM NEVER sets HP/damage/XP. The backend computes them from question
difficulty + encounter kind + designer constants, so balance stays stable and
exploit-resistant. Sizing rule: an encounter's enemy HP ≈ the total damage a
player deals by answering its questions correctly (× a kind multiplier), so a
near-perfect run wins and a few mistakes still leave it winnable.
"""

from __future__ import annotations

from app.schemas.game import (
    CombatConfig,
    EncounterCombat,
    EncounterKind,
    Question,
    Reward,
    RewardKind,
)

# Per-question difficulty weighting applied to baseDamagePerCorrect.
_DIFFICULTY_WEIGHT = {"easy": 0.8, "medium": 1.0, "hard": 1.3}
# Enemy HP scales by encounter kind (also exposed on EncounterCombat).
_KIND_HP_MULT = {"minion": 1.0, "elite": 1.5, "boss": 2.0}

# Small authored relic catalog (the LLM may theme names later; magnitudes are ours).
_BOSS_RELIC = Reward(
    rewardId="relic_focus",
    kind=RewardKind.relic,
    name="Scholar's Focus",
    description="+25% damage while your streak is 3 or higher.",
    magnitude=25,
)
_ELITE_REWARD = Reward(
    rewardId="powerup_insight",
    kind=RewardKind.powerup,
    name="Flash of Insight",
    description="Reveal one wrong answer once per encounter.",
    magnitude=1,
)


def default_combat_config() -> CombatConfig:
    return CombatConfig()


def compute_encounter_combat(
    questions: list[Question], kind: EncounterKind, cfg: CombatConfig
) -> EncounterCombat:
    kind_value = kind.value if isinstance(kind, EncounterKind) else str(kind)
    expected_damage = sum(
        cfg.baseDamagePerCorrect * _DIFFICULTY_WEIGHT[q.difficulty.value] for q in questions
    )
    if expected_damage <= 0:
        expected_damage = float(cfg.baseDamagePerCorrect)
    mult = _KIND_HP_MULT.get(kind_value, 1.0)
    return EncounterCombat(
        enemyMaxHp=max(1, round(expected_damage * mult)),
        enemyBaseDamage=cfg.wrongAnswerHpCost,
        kindHpMultiplier=mult,
    )


def rewards_for_encounter(kind: EncounterKind) -> list[Reward]:
    kind_value = kind.value if isinstance(kind, EncounterKind) else str(kind)
    if kind_value == "boss":
        return [_BOSS_RELIC.model_copy()]
    if kind_value == "elite":
        return [_ELITE_REWARD.model_copy()]
    return []


def xp_for_question(q: Question, cfg: CombatConfig) -> int:
    return getattr(cfg.xpPerCorrectByDifficulty, q.difficulty.value)
