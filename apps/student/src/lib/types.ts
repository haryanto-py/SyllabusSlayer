// Types for the redacted "play" game the backend serves (no answer fields) and the
// per-answer scoring result. Mirrors backend/app/services/scoring.py output.

export type QuestionType =
  | "multiple_choice"
  | "multi_select"
  | "true_false"
  | "short_answer"
  | "ordering"
  | "matching";

export interface PlayOption {
  optionId: string;
  text: string;
}

export interface PlayOrderedItem {
  itemId: string;
  text: string;
}

export interface PlayQuestion {
  questionId: string;
  questionType: QuestionType;
  bloomLevel: string;
  difficulty: string;
  prompt: string;
  hint: string | null;
  options?: PlayOption[] | null;
  orderedItems?: PlayOrderedItem[] | null;
  matchLeft?: { pairId: string; left: string }[] | null;
  matchRight?: string[] | null;
}

export interface PlayCombat {
  enemyMaxHp: number;
  enemyBaseDamage: number;
  kindHpMultiplier: number;
}

export interface PlayReward {
  rewardId: string;
  kind: string;
  name: string;
  description: string;
  magnitude: number;
}

export interface PlayEncounter {
  encounterId: string;
  order: number;
  kind: string;
  title: string;
  enemyName: string;
  enemyFlavor: string;
  subTopic: string;
  combat: PlayCombat;
  rewards: PlayReward[];
  questions: PlayQuestion[];
}

export interface MapNode {
  nodeId: string;
  row: number;
  col: number;
  type: "battle" | "rest" | "boss";
  encounterId: string | null;
  kind: string | null;
  title: string;
}

export interface RunMap {
  nodes: MapNode[];
  edges: { from: string; to: string }[];
  restHealPct: number;
}

export interface PlayAct {
  actId: string;
  order: number;
  title: string;
  syllabusTopic: string;
  summary: string;
  encounters: PlayEncounter[];
  map: RunMap;
}

export interface CombatConfig {
  playerStartingHp: number;
  baseDamagePerCorrect: number;
  streakMultipliers: number[];
  wrongAnswerHpCost: number;
  xpPerCorrectByDifficulty: { easy: number; medium: number; hard: number };
  levelXpCurve: number[];
}

export interface PlayGame {
  schemaVersion: string;
  campaignId: string;
  title: string;
  description: string;
  sourceDocumentId: string;
  combatConfig: CombatConfig;
  acts: PlayAct[];
}

export interface StartResponse {
  session_id: string;
  combatConfig: CombatConfig;
  game: PlayGame;
}

export interface AnswerResult {
  isCorrect: boolean;
  correctAnswer: unknown;
  explanation: string | null;
  sourceQuote: string | null;
  sourcePage: number | null;
  damage: number;
  streak: number;
  hp: number;
  maxHp: number;
  score: number;
  xp: number;
  level: number;
  playerDown: boolean;
}

export interface FinishResult {
  status: string;
  score: number;
  xp: number;
  hp: number;
  level: number;
}

export interface Relic {
  relicId: string;
  name: string;
  icon: string;
  rarity: string;
  description: string;
}

export interface RestResult {
  hp: number;
  maxHp: number;
  healed: number;
}

export interface RewardResult {
  relics: Relic[];
  hp: number;
  maxHp: number;
}
