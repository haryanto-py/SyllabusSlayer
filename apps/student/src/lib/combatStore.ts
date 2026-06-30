// Client combat state (Zustand). The server is authoritative for correctness/scoring;
// this store sequences the UI: present a question → submit → apply the server's verdict
// (enemy HP, player HP/streak/XP) → advance / clear encounter / win / lose.
// (A lightweight phase machine — graduates to XState if relics/phases get complex.)
import { create } from "zustand";

import { finishPlay, startPlay, submitAnswer } from "./play";
import type { AnswerResult, CombatConfig, PlayEncounter, PlayGame, PlayQuestion } from "./types";

export type Phase = "idle" | "loading" | "presenting" | "feedback" | "victory" | "defeat" | "error";

interface PlayerState {
  hp: number;
  maxHp: number;
  streak: number;
  xp: number;
  level: number;
  score: number;
}

interface CombatState {
  phase: Phase;
  error: string | null;
  submitting: boolean;
  sessionId: string | null;
  game: PlayGame | null;
  combatConfig: CombatConfig | null;
  actIndex: number;
  encounterIndex: number;
  questionIndex: number;
  enemyHp: number;
  enemyMaxHp: number;
  player: PlayerState;
  lastResult: AnswerResult | null;
  encountersCleared: number;

  start: (campaignId: string) => Promise<void>;
  submit: (answer: unknown) => Promise<void>;
  advance: () => void;
  reset: () => void;
  currentEncounter: () => PlayEncounter | null;
  currentQuestion: () => PlayQuestion | null;
  totalEncounters: () => number;
}

function firstPlayable(game: PlayGame): { a: number; e: number } | null {
  for (let a = 0; a < game.acts.length; a++) {
    for (let e = 0; e < game.acts[a].encounters.length; e++) {
      if (game.acts[a].encounters[e].questions.length > 0) return { a, e };
    }
  }
  return null;
}

function nextLocation(game: PlayGame, a: number, e: number): { a: number; e: number } | null {
  if (game.acts[a] && e + 1 < game.acts[a].encounters.length) return { a, e: e + 1 };
  for (let na = a + 1; na < game.acts.length; na++) {
    if (game.acts[na].encounters.length > 0) return { a: na, e: 0 };
  }
  return null;
}

export const useCombat = create<CombatState>()((set, get) => ({
  phase: "idle",
  error: null,
  submitting: false,
  sessionId: null,
  game: null,
  combatConfig: null,
  actIndex: 0,
  encounterIndex: 0,
  questionIndex: 0,
  enemyHp: 0,
  enemyMaxHp: 0,
  player: { hp: 0, maxHp: 0, streak: 0, xp: 0, level: 1, score: 0 },
  lastResult: null,
  encountersCleared: 0,

  currentEncounter: () => {
    const { game, actIndex, encounterIndex } = get();
    return game?.acts[actIndex]?.encounters[encounterIndex] ?? null;
  },
  currentQuestion: () => get().currentEncounter()?.questions[get().questionIndex] ?? null,
  totalEncounters: () =>
    get().game?.acts.reduce((n, act) => n + act.encounters.length, 0) ?? 0,

  start: async (campaignId) => {
    set({ phase: "loading", error: null, encountersCleared: 0 });
    try {
      const res = await startPlay(campaignId);
      const loc = firstPlayable(res.game);
      if (!loc) {
        set({ phase: "error", error: "This campaign has no playable questions yet." });
        return;
      }
      const enc = res.game.acts[loc.a].encounters[loc.e];
      const cfg = res.combatConfig;
      set({
        sessionId: res.session_id,
        game: res.game,
        combatConfig: cfg,
        actIndex: loc.a,
        encounterIndex: loc.e,
        questionIndex: 0,
        enemyHp: enc.combat.enemyMaxHp,
        enemyMaxHp: enc.combat.enemyMaxHp,
        player: {
          hp: cfg.playerStartingHp,
          maxHp: cfg.playerStartingHp,
          streak: 0,
          xp: 0,
          level: 1,
          score: 0,
        },
        lastResult: null,
        phase: "presenting",
      });
    } catch (e) {
      set({ phase: "error", error: e instanceof Error ? e.message : String(e) });
    }
  },

  submit: async (answer) => {
    const { sessionId, submitting } = get();
    const enc = get().currentEncounter();
    const q = get().currentQuestion();
    if (!sessionId || !enc || !q || submitting) return;
    set({ submitting: true });
    try {
      const res = await submitAnswer(sessionId, {
        encounter_id: enc.encounterId,
        question_id: q.questionId,
        answer,
      });
      set((s) => ({
        submitting: false,
        lastResult: res,
        enemyHp: Math.max(0, s.enemyHp - res.damage),
        player: {
          ...s.player,
          hp: res.hp,
          streak: res.streak,
          xp: res.xp,
          level: res.level,
          score: res.score,
        },
        phase: "feedback",
      }));
    } catch (e) {
      set({ submitting: false, phase: "error", error: e instanceof Error ? e.message : String(e) });
    }
  },

  advance: () => {
    const s = get();
    if (!s.game) return;
    if (s.player.hp <= 0) {
      set({ phase: "defeat" });
      if (s.sessionId) finishPlay(s.sessionId).catch(() => {});
      return;
    }
    const enc = s.currentEncounter();
    const cleared = s.enemyHp <= 0 || !enc || s.questionIndex + 1 >= enc.questions.length;
    if (!cleared) {
      set({ phase: "presenting", questionIndex: s.questionIndex + 1, lastResult: null });
      return;
    }
    const loc = nextLocation(s.game, s.actIndex, s.encounterIndex);
    if (!loc) {
      set({ phase: "victory", encountersCleared: s.encountersCleared + 1 });
      if (s.sessionId) finishPlay(s.sessionId).catch(() => {});
      return;
    }
    const nextEnc = s.game.acts[loc.a].encounters[loc.e];
    set({
      actIndex: loc.a,
      encounterIndex: loc.e,
      questionIndex: 0,
      enemyHp: nextEnc.combat.enemyMaxHp,
      enemyMaxHp: nextEnc.combat.enemyMaxHp,
      lastResult: null,
      phase: "presenting",
      encountersCleared: s.encountersCleared + 1,
    });
  },

  reset: () =>
    set({ phase: "idle", error: null, sessionId: null, game: null, lastResult: null, submitting: false }),
}));
