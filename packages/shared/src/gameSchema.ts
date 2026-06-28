/**
 * Zod mirror of the backend game-content schema (backend/app/schemas/game.py).
 * Keep these two in sync. Validates the AI-generated game JSON on the client and
 * gives compile-time types for the combat renderer.
 *
 * Questions arrive in the flat "all fields present, null when unused" form (so the
 * data maps cleanly onto OpenAI Structured Outputs). The per-type `.refine` checks
 * mirror the backend validator; the renderer narrows on `questionType`.
 */
import { z } from "zod";

export const QuestionType = z.enum([
  "multiple_choice",
  "multi_select",
  "true_false",
  "short_answer",
  "ordering",
  "matching",
]);
export type QuestionType = z.infer<typeof QuestionType>;

export const BloomLevel = z.enum([
  "remember",
  "understand",
  "apply",
  "analyze",
  "evaluate",
  "create",
]);
export const Difficulty = z.enum(["easy", "medium", "hard"]);
export const EncounterKind = z.enum(["minion", "elite", "boss"]);
export const RewardKind = z.enum(["relic", "powerup", "xp", "heal"]);

export const OptionSchema = z.object({ optionId: z.string(), text: z.string() });
export const OrderedItemSchema = z.object({
  itemId: z.string(),
  text: z.string(),
  order: z.number().int(),
});
export const MatchPairSchema = z.object({
  pairId: z.string(),
  left: z.string(),
  right: z.string(),
});

const QuestionBase = z.object({
  questionId: z.string(),
  questionType: QuestionType,
  bloomLevel: BloomLevel,
  difficulty: Difficulty,
  prompt: z.string(),
  // source grounding
  sourceChunkIds: z.array(z.string()),
  sourceQuote: z.string(),
  sourcePage: z.number().int().nullable(),
  // feedback
  explanation: z.string(),
  hint: z.string().nullable(),
  // per-type clusters (exactly one non-null per questionType)
  options: z.array(OptionSchema).nullable(),
  correctOptionIds: z.array(z.string()).nullable(),
  correctBoolean: z.boolean().nullable(),
  acceptedAnswers: z.array(z.string()).nullable(),
  caseSensitive: z.boolean().nullable(),
  orderedItems: z.array(OrderedItemSchema).nullable(),
  matchPairs: z.array(MatchPairSchema).nullable(),
});

export const QuestionSchema = QuestionBase.refine(
  (q) =>
    !["multiple_choice", "multi_select"].includes(q.questionType) ||
    (!!q.options?.length && !!q.correctOptionIds?.length),
  { message: "choice questions require options and correctOptionIds" },
)
  .refine(
    (q) => q.questionType !== "multiple_choice" || q.correctOptionIds?.length === 1,
    { message: "multiple_choice requires exactly one correct option" },
  )
  .refine((q) => q.questionType !== "true_false" || q.correctBoolean !== null, {
    message: "true_false requires correctBoolean",
  })
  .refine((q) => q.questionType !== "short_answer" || !!q.acceptedAnswers?.length, {
    message: "short_answer requires acceptedAnswers",
  })
  .refine((q) => q.questionType !== "ordering" || !!q.orderedItems?.length, {
    message: "ordering requires orderedItems",
  })
  .refine((q) => q.questionType !== "matching" || !!q.matchPairs?.length, {
    message: "matching requires matchPairs",
  });
export type Question = z.infer<typeof QuestionSchema>;

// --- staged generation outputs ---
export const QuestionBatchSchema = z.object({
  encounterId: z.string(),
  questions: z.array(QuestionSchema),
});

export const EncounterStubSchema = z.object({
  encounterId: z.string(),
  order: z.number().int(),
  kind: EncounterKind,
  title: z.string(),
  enemyName: z.string(),
  enemyFlavor: z.string(),
  subTopic: z.string(),
  targetQuestionCount: z.number().int(),
});
export const ActStubSchema = z.object({
  actId: z.string(),
  order: z.number().int(),
  title: z.string(),
  syllabusTopic: z.string(),
  summary: z.string(),
  encounters: z.array(EncounterStubSchema),
});
export const CampaignOutlineSchema = z.object({
  schemaVersion: z.string(),
  campaignId: z.string(),
  title: z.string(),
  description: z.string(),
  sourceDocumentId: z.string(),
  acts: z.array(ActStubSchema),
});
export type CampaignOutline = z.infer<typeof CampaignOutlineSchema>;

// --- combat / RPG tuning (backend-computed) ---
export const CombatConfigSchema = z.object({
  playerStartingHp: z.number().int(),
  baseDamagePerCorrect: z.number().int(),
  streakMultipliers: z.array(z.number()),
  wrongAnswerHpCost: z.number().int(),
  xpPerCorrectByDifficulty: z.object({
    easy: z.number().int(),
    medium: z.number().int(),
    hard: z.number().int(),
  }),
  levelXpCurve: z.array(z.number().int()),
});
export type CombatConfig = z.infer<typeof CombatConfigSchema>;

export const EncounterCombatSchema = z.object({
  enemyMaxHp: z.number().int(),
  enemyBaseDamage: z.number().int(),
  kindHpMultiplier: z.number(),
});
export const RewardSchema = z.object({
  rewardId: z.string(),
  kind: RewardKind,
  name: z.string(),
  description: z.string(),
  magnitude: z.number().int(),
});

export const SCHEMA_VERSION = "1.0.0";
