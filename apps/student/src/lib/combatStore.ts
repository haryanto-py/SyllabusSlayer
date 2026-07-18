// Client run state (Zustand). The server is authoritative for correctness, scoring, HP, and
// relics; this store drives the run: navigate the act's map → fight the chosen encounter →
// pick a relic reward → return to the map → the boss clears the act → next act, or victory.
import { create } from "zustand";

import { finishPlay, rest, rewardOptions, startPlay, submitAnswer, takeReward } from "./play";
import type {
  AnswerResult,
  CombatConfig,
  MapNode,
  PlayAct,
  PlayEncounter,
  PlayGame,
  Relic,
  RunSummary,
} from "./types";

export type Phase =
  | "idle"
  | "loading"
  | "map"
  | "presenting"
  | "feedback"
  | "reward"
  | "victory"
  | "defeat"
  | "error";

interface PlayerState {
  hp: number;
  maxHp: number;
  streak: number;
  xp: number;
  level: number;
  score: number;
  relics: Relic[];
}

interface CombatState {
  phase: Phase;
  error: string | null;
  submitting: boolean;
  sessionId: string | null;
  game: PlayGame | null;
  combatConfig: CombatConfig | null;
  actIndex: number;

  // map navigation (per act)
  currentNodeId: string | null; // last cleared node this act (null = act start)
  clearedNodeIds: string[];
  lastRestHeal: number | null;

  // active encounter (during a battle)
  activeNodeId: string | null;
  questionIndex: number;
  enemyHp: number;
  enemyMaxHp: number;
  player: PlayerState;
  lastResult: AnswerResult | null;

  // relic reward (after a cleared battle/boss)
  rewardOptions: Relic[];
  lastClearedBoss: boolean;

  // server-authoritative run-end summary (meta-progression, M5.3)
  runSummary: RunSummary | null;

  start: (campaignId: string) => Promise<void>;
  selectNode: (nodeId: string) => Promise<void>;
  submit: (answer: unknown) => Promise<void>;
  advance: () => Promise<void>;
  chooseReward: (relicId: string | null) => Promise<void>;
  reset: () => void;

  act: () => PlayAct | null;
  reachable: () => MapNode[];
  activeEncounter: () => PlayEncounter | null;
  totalActs: () => number;
}

export const useCombat = create<CombatState>()((set, get) => ({
  phase: "idle",
  error: null,
  submitting: false,
  sessionId: null,
  game: null,
  combatConfig: null,
  actIndex: 0,
  currentNodeId: null,
  clearedNodeIds: [],
  lastRestHeal: null,
  activeNodeId: null,
  questionIndex: 0,
  enemyHp: 0,
  enemyMaxHp: 0,
  player: { hp: 0, maxHp: 0, streak: 0, xp: 0, level: 1, score: 0, relics: [] },
  lastResult: null,
  rewardOptions: [],
  lastClearedBoss: false,
  runSummary: null,

  act: () => get().game?.acts[get().actIndex] ?? null,
  totalActs: () => get().game?.acts.length ?? 0,
  activeEncounter: () => {
    const act = get().act();
    const node = act?.map.nodes.find((n) => n.nodeId === get().activeNodeId);
    return act?.encounters.find((e) => e.encounterId === node?.encounterId) ?? null;
  },
  reachable: () => {
    const act = get().act();
    if (!act) return [];
    const cleared = new Set(get().clearedNodeIds);
    const { currentNodeId } = get();
    if (currentNodeId == null) {
      const hasIncoming = new Set(act.map.edges.map((e) => e.to));
      return act.map.nodes.filter((n) => !hasIncoming.has(n.nodeId) && !cleared.has(n.nodeId));
    }
    const successorIds = new Set(
      act.map.edges.filter((e) => e.from === currentNodeId).map((e) => e.to),
    );
    return act.map.nodes.filter((n) => successorIds.has(n.nodeId) && !cleared.has(n.nodeId));
  },

  start: async (campaignId) => {
    set({ phase: "loading", error: null });
    try {
      const res = await startPlay(campaignId);
      const cfg = res.combatConfig;
      if (!res.game.acts.length) {
        set({ phase: "error", error: "This campaign has no content yet." });
        return;
      }
      set({
        sessionId: res.session_id,
        game: res.game,
        combatConfig: cfg,
        actIndex: 0,
        currentNodeId: null,
        clearedNodeIds: [],
        lastRestHeal: null,
        activeNodeId: null,
        questionIndex: 0,
        lastResult: null,
        rewardOptions: [],
        lastClearedBoss: false,
        runSummary: null,
        player: {
          // server may seed a meta HP bonus (M5.3); fall back to base for older backends
          hp: res.hp ?? cfg.playerStartingHp,
          maxHp: res.maxHp ?? cfg.playerStartingHp,
          streak: 0,
          xp: 0,
          level: 1,
          score: 0,
          relics: [],
        },
        phase: "map",
      });
    } catch (e) {
      set({ phase: "error", error: e instanceof Error ? e.message : String(e) });
    }
  },

  selectNode: async (nodeId) => {
    const act = get().act();
    const node = act?.map.nodes.find((n) => n.nodeId === nodeId);
    const sessionId = get().sessionId;
    if (!act || !node || !sessionId) return;
    if (!get().reachable().some((n) => n.nodeId === nodeId)) return; // not a legal move

    if (node.type === "rest") {
      // Server-authoritative heal so the next /answer doesn't clobber the restored HP.
      try {
        const res = await rest(sessionId);
        set((s) => ({
          player: { ...s.player, hp: res.hp, maxHp: res.maxHp },
          clearedNodeIds: [...s.clearedNodeIds, nodeId],
          currentNodeId: nodeId,
          lastRestHeal: res.healed,
          phase: "map",
        }));
      } catch (e) {
        set({ phase: "error", error: e instanceof Error ? e.message : String(e) });
      }
      return;
    }

    const enc = act.encounters.find((e) => e.encounterId === node.encounterId);
    if (!enc) return;
    set({
      activeNodeId: nodeId,
      questionIndex: 0,
      enemyHp: enc.combat.enemyMaxHp,
      enemyMaxHp: enc.combat.enemyMaxHp,
      lastResult: null,
      lastRestHeal: null,
      phase: "presenting",
    });
  },

  submit: async (answer) => {
    const { sessionId, submitting } = get();
    const enc = get().activeEncounter();
    const q = enc?.questions[get().questionIndex];
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
          maxHp: res.maxHp,
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

  advance: async () => {
    const s = get();
    if (!s.game) return;
    if (s.player.hp <= 0) {
      // Server already banked + marked the run defeated on the killing /answer; finish here is
      // idempotent and returns the persisted meta summary for the death screen. Set phase first
      // so the UI isn't blocked on the request, then patch in the summary.
      set({ phase: "defeat" });
      if (s.sessionId) {
        try {
          const summary = await finishPlay(s.sessionId);
          set({ runSummary: summary });
        } catch {
          /* leave runSummary null → ResultScreen falls back to in-memory player */
        }
      }
      return;
    }
    const enc = s.activeEncounter();
    const encounterCleared = s.enemyHp <= 0 || !enc || s.questionIndex + 1 >= enc.questions.length;
    if (!encounterCleared) {
      set({ phase: "presenting", questionIndex: s.questionIndex + 1, lastResult: null });
      return;
    }
    // node cleared → offer a relic reward before advancing
    const act = s.act();
    const node = act?.map.nodes.find((n) => n.nodeId === s.activeNodeId);
    const cleared = [...s.clearedNodeIds, s.activeNodeId].filter(Boolean) as string[];
    set({
      clearedNodeIds: cleared,
      currentNodeId: s.activeNodeId,
      lastClearedBoss: node?.type === "boss",
      lastResult: null,
      rewardOptions: [],
      phase: "reward",
    });
    try {
      const { options } = await rewardOptions(s.sessionId!, s.activeNodeId ?? "");
      set({ rewardOptions: options });
    } catch {
      set({ rewardOptions: [] });
    }
  },

  chooseReward: async (relicId) => {
    const { sessionId } = get();
    if (relicId && sessionId) {
      try {
        const res = await takeReward(sessionId, relicId);
        set((s) => ({
          player: { ...s.player, relics: res.relics, hp: res.hp, maxHp: res.maxHp },
        }));
      } catch (e) {
        set({ phase: "error", error: e instanceof Error ? e.message : String(e) });
        return;
      }
    }
    const s = get();
    if (s.lastClearedBoss) {
      const next = s.actIndex + 1;
      if (s.game && next < s.game.acts.length) {
        set({
          actIndex: next,
          currentNodeId: null,
          clearedNodeIds: [],
          activeNodeId: null,
          rewardOptions: [],
          lastResult: null,
          phase: "map",
        });
      } else {
        // final boss cleared → victory. finish_play banks the run and returns the meta summary.
        set({ phase: "victory", activeNodeId: null, rewardOptions: [] });
        if (s.sessionId) {
          try {
            const summary = await finishPlay(s.sessionId);
            set({ runSummary: summary });
          } catch {
            /* leave runSummary null → ResultScreen falls back to in-memory player */
          }
        }
      }
      return;
    }
    set({ activeNodeId: null, rewardOptions: [], phase: "map" });
  },

  reset: () =>
    set({
      phase: "idle",
      error: null,
      sessionId: null,
      game: null,
      lastResult: null,
      submitting: false,
      runSummary: null,
    }),
}));
