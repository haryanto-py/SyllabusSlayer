// Client run state (Zustand). The server is authoritative for correctness/scoring; this
// store drives the run: navigate the act's map → fight the chosen encounter → return to
// the map → the boss node clears the act → next act, or victory. HP persists across the run.
import { create } from "zustand";

import { finishPlay, startPlay, submitAnswer } from "./play";
import type {
  AnswerResult,
  CombatConfig,
  MapNode,
  PlayAct,
  PlayEncounter,
  PlayGame,
} from "./types";

export type Phase =
  | "idle"
  | "loading"
  | "map"
  | "presenting"
  | "feedback"
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

  start: (campaignId: string) => Promise<void>;
  selectNode: (nodeId: string) => Promise<void>;
  submit: (answer: unknown) => Promise<void>;
  advance: () => void;
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
  player: { hp: 0, maxHp: 0, streak: 0, xp: 0, level: 1, score: 0 },
  lastResult: null,

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
        player: {
          hp: cfg.playerStartingHp,
          maxHp: cfg.playerStartingHp,
          streak: 0,
          xp: 0,
          level: 1,
          score: 0,
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
    if (!act || !node) return;
    if (!get().reachable().some((n) => n.nodeId === nodeId)) return; // not a legal move

    if (node.type === "rest") {
      const { player } = get();
      const heal = Math.ceil((player.maxHp * act.map.restHealPct) / 100);
      set((s) => ({
        player: { ...s.player, hp: Math.min(player.maxHp, player.hp + heal) },
        clearedNodeIds: [...s.clearedNodeIds, nodeId],
        currentNodeId: nodeId,
        lastRestHeal: heal,
        phase: "map",
      }));
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
    const enc = s.activeEncounter();
    const encounterCleared = s.enemyHp <= 0 || !enc || s.questionIndex + 1 >= enc.questions.length;
    if (!encounterCleared) {
      set({ phase: "presenting", questionIndex: s.questionIndex + 1, lastResult: null });
      return;
    }
    // node cleared
    const act = s.act();
    const node = act?.map.nodes.find((n) => n.nodeId === s.activeNodeId);
    const cleared = [...s.clearedNodeIds, s.activeNodeId].filter(Boolean) as string[];
    if (node?.type === "boss") {
      const next = s.actIndex + 1;
      if (next < s.game.acts.length) {
        set({
          actIndex: next,
          currentNodeId: null,
          clearedNodeIds: [],
          activeNodeId: null,
          lastResult: null,
          phase: "map",
        });
      } else {
        set({ phase: "victory", activeNodeId: null });
        if (s.sessionId) finishPlay(s.sessionId).catch(() => {});
      }
      return;
    }
    set({
      clearedNodeIds: cleared,
      currentNodeId: s.activeNodeId,
      activeNodeId: null,
      lastResult: null,
      phase: "map",
    });
  },

  reset: () =>
    set({ phase: "idle", error: null, sessionId: null, game: null, lastResult: null, submitting: false }),
}));
