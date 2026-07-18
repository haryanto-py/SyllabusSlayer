"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState, useSyncExternalStore } from "react";

import { type Phase, useCombat } from "@/lib/combatStore";
import type { PlayQuestion } from "@/lib/types";
import * as sfx from "@/game/sfx";

import BattleCanvas, { ENEMY_EMOJI } from "./BattleCanvas";
import { PlayerHud } from "./HpBar";
import MapView from "./MapView";
import RewardScreen from "./RewardScreen";

export default function Combat({ campaignId }: { campaignId: string }) {
  const phase = useCombat((s) => s.phase);
  const start = useCombat((s) => s.start);
  const reset = useCombat((s) => s.reset);

  useEffect(() => {
    start(campaignId);
    return () => reset();
  }, [campaignId, start, reset]);

  return (
    <div className="relative flex flex-1 flex-col">
      <SoundToggle />
      <AnimatePresence mode="wait">
        <motion.div
          key={screenKey(phase)}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="flex flex-1 flex-col"
        >
          <Screen phase={phase} />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

// Coarse screen id so presenting<->feedback (both the arena) don't trigger a full crossfade.
function screenKey(phase: Phase): string {
  if (phase === "presenting" || phase === "feedback") return "arena";
  if (phase === "idle" || phase === "loading") return "loading";
  if (phase === "victory" || phase === "defeat") return "result";
  return phase; // map | reward | error
}

function Screen({ phase }: { phase: Phase }) {
  if (phase === "idle" || phase === "loading") return <Centered>⚔️ Summoning your campaign…</Centered>;
  if (phase === "error") return <ErrorView />;
  if (phase === "victory" || phase === "defeat") return <ResultScreen />;
  if (phase === "reward") return <RewardScreen />;
  if (phase === "map") return <MapView />;
  return <Arena />;
}

function SoundToggle() {
  // external (localStorage) state — read via useSyncExternalStore so SSR renders 🔊 and the client
  // syncs without a hydration mismatch or a setState-in-effect.
  const muted = useSyncExternalStore(sfx.subscribeMuted, sfx.isMuted, () => false);
  return (
    <button
      onClick={() => sfx.toggleMuted()}
      aria-label={muted ? "Unmute sound" : "Mute sound"}
      className="absolute right-3 top-3 z-10 rounded-full border border-zinc-700 bg-zinc-900/80 px-2.5 py-1 text-sm text-zinc-300 transition-colors hover:bg-zinc-800"
    >
      {muted ? "🔇" : "🔊"}
    </button>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-1 items-center justify-center px-6 text-zinc-300">{children}</div>;
}

function ErrorView() {
  const error = useCombat((s) => s.error);
  return (
    <Centered>
      <div className="max-w-md text-center">
        <p className="text-rose-300">{error ?? "Something went wrong."}</p>
        <Link href="/" className="mt-4 inline-block text-amber-400 hover:underline">
          ← Back
        </Link>
      </div>
    </Centered>
  );
}

function Arena() {
  const enc = useCombat((s) => s.activeEncounter());
  const enemyHp = useCombat((s) => s.enemyHp);
  const enemyMaxHp = useCombat((s) => s.enemyMaxHp);
  const player = useCombat((s) => s.player);
  const phase = useCombat((s) => s.phase);
  const questionIndex = useCombat((s) => s.questionIndex);
  const lastResult = useCombat((s) => s.lastResult);

  if (!enc) return <Centered>…</Centered>;

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-4 px-5 py-6">
      <div className="flex items-start justify-between">
        <div>
          <span className="rounded bg-rose-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase text-rose-300">
            {enc.kind}
          </span>
          <h2 className="mt-1 text-lg font-bold text-zinc-100">{enc.enemyName}</h2>
          <p className="text-xs italic text-zinc-400">{enc.enemyFlavor}</p>
        </div>
        <div className="text-right text-xs text-zinc-400">
          HP {enemyHp}/{enemyMaxHp}
        </div>
      </div>

      {/* Phaser battle arena: sprites + HP bars + juice (hit-stop / shake / particles). Purely
          presentational — the DOM question card below stays the accessible source of truth. */}
      <BattleCanvas
        enemyName={enc.enemyName}
        enemyEmoji={ENEMY_EMOJI[enc.kind] ?? "👾"}
        enemyFrac={enemyMaxHp > 0 ? enemyHp / enemyMaxHp : 0}
        playerFrac={player.maxHp > 0 ? player.hp / player.maxHp : 0}
        lastResult={lastResult}
        streak={player.streak}
      />

      <PlayerHud player={player} />

      <AnimatePresence mode="wait">
        {phase === "feedback" || !enc.questions[questionIndex] ? (
          <Feedback key="fb" />
        ) : (
          <QuestionView
            key={`q-${enc.encounterId}-${questionIndex}`}
            question={enc.questions[questionIndex]}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function QuestionView({ question }: { question: PlayQuestion }) {
  const submit = useCombat((s) => s.submit);
  const submitting = useCombat((s) => s.submitting);
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5"
    >
      <div className="mb-1 flex gap-2 text-[10px] uppercase tracking-wide text-zinc-500">
        <span>{question.questionType.replace("_", " ")}</span>
        <span>· {question.bloomLevel}</span>
        <span>· {question.difficulty}</span>
      </div>
      <p className="mb-4 text-base font-medium text-zinc-100">{question.prompt}</p>
      <AnswerInput question={question} disabled={submitting} onSubmit={submit} />
      {question.hint && <p className="mt-3 text-xs text-zinc-500">💡 {question.hint}</p>}
    </motion.div>
  );
}

function AnswerInput({
  question,
  disabled,
  onSubmit,
}: {
  question: PlayQuestion;
  disabled: boolean;
  onSubmit: (answer: unknown) => void;
}) {
  const [multi, setMulti] = useState<string[]>([]);
  const [text, setText] = useState("");
  const [order, setOrder] = useState<string[]>([]);
  const [pairs, setPairs] = useState<Record<string, string>>({});
  const btn =
    "w-full rounded-lg border border-zinc-700 bg-zinc-800/70 px-4 py-3 text-left text-zinc-100 transition-colors hover:border-amber-500/60 hover:bg-zinc-800 disabled:opacity-50";

  switch (question.questionType) {
    case "multiple_choice":
      return (
        <div className="flex flex-col gap-2">
          {(question.options ?? []).map((o) => (
            <button key={o.optionId} disabled={disabled} className={btn} onClick={() => onSubmit(o.optionId)}>
              {o.text}
            </button>
          ))}
        </div>
      );
    case "true_false":
      return (
        <div className="flex gap-3">
          <button disabled={disabled} className={btn} onClick={() => onSubmit(true)}>
            ✓ True
          </button>
          <button disabled={disabled} className={btn} onClick={() => onSubmit(false)}>
            ✗ False
          </button>
        </div>
      );
    case "multi_select":
      return (
        <div className="flex flex-col gap-2">
          {(question.options ?? []).map((o) => {
            const on = multi.includes(o.optionId);
            return (
              <button
                key={o.optionId}
                disabled={disabled}
                className={`${btn} ${on ? "border-amber-500 bg-amber-500/10" : ""}`}
                onClick={() => setMulti((m) => (on ? m.filter((x) => x !== o.optionId) : [...m, o.optionId]))}
              >
                {on ? "☑ " : "☐ "}
                {o.text}
              </button>
            );
          })}
          <SubmitBtn disabled={disabled || multi.length === 0} onClick={() => onSubmit(multi)} />
        </div>
      );
    case "short_answer":
      return (
        <div className="flex gap-2">
          <input
            value={text}
            disabled={disabled}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && text.trim() && onSubmit(text.trim())}
            placeholder="Type your answer…"
            className="flex-1 rounded-lg border border-zinc-700 bg-zinc-800/70 px-4 py-3 text-zinc-100"
          />
          <SubmitBtn disabled={disabled || !text.trim()} onClick={() => onSubmit(text.trim())} />
        </div>
      );
    case "ordering":
      return (
        <div className="flex flex-col gap-2">
          {(question.orderedItems ?? []).map((it) => {
            const pos = order.indexOf(it.itemId);
            return (
              <button
                key={it.itemId}
                disabled={disabled || pos !== -1}
                className={`${btn} ${pos !== -1 ? "border-amber-500 bg-amber-500/10" : ""}`}
                onClick={() => setOrder((o) => [...o, it.itemId])}
              >
                {pos !== -1 ? `${pos + 1}. ` : "• "}
                {it.text}
              </button>
            );
          })}
          <div className="flex gap-2">
            <button
              disabled={disabled || order.length === 0}
              className="rounded-lg border border-zinc-700 px-3 py-2 text-sm text-zinc-400 disabled:opacity-40"
              onClick={() => setOrder([])}
            >
              Reset
            </button>
            <SubmitBtn
              disabled={disabled || order.length !== (question.orderedItems ?? []).length}
              onClick={() => onSubmit(order)}
            />
          </div>
        </div>
      );
    case "matching":
      return (
        <div className="flex flex-col gap-2">
          {(question.matchLeft ?? []).map((l) => (
            <div key={l.pairId} className="flex items-center gap-2">
              <span className="flex-1 text-zinc-200">{l.left}</span>
              <select
                disabled={disabled}
                className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-2 text-zinc-100"
                value={pairs[l.pairId] ?? ""}
                onChange={(e) => setPairs((p) => ({ ...p, [l.pairId]: e.target.value }))}
              >
                <option value="">— pick —</option>
                {(question.matchRight ?? []).map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
          ))}
          <SubmitBtn
            disabled={disabled || Object.keys(pairs).length !== (question.matchLeft ?? []).length}
            onClick={() => onSubmit(pairs)}
          />
        </div>
      );
    default:
      return <p className="text-sm text-zinc-500">Unsupported question type.</p>;
  }
}

function SubmitBtn({ disabled, onClick }: { disabled: boolean; onClick: () => void }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className="rounded-lg bg-amber-500 px-5 py-3 font-semibold text-zinc-950 transition-opacity hover:bg-amber-400 disabled:opacity-40"
    >
      Attack ⚔️
    </button>
  );
}

function Feedback() {
  const result = useCombat((s) => s.lastResult);
  const advance = useCombat((s) => s.advance);
  if (!result) return null;
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0 }}
      className={`rounded-2xl border p-5 ${
        result.isCorrect ? "border-emerald-700/60 bg-emerald-950/30" : "border-rose-800/60 bg-rose-950/30"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className={`font-bold ${result.isCorrect ? "text-emerald-300" : "text-rose-300"}`}>
          {result.isCorrect ? `Hit! −${result.damage} enemy HP` : "Missed — you took damage"}
        </span>
        {result.isCorrect && result.streak > 1 && (
          <span className="text-amber-300">🔥 ×{result.streak} streak</span>
        )}
      </div>
      {result.explanation && <p className="mt-2 text-sm text-zinc-300">{result.explanation}</p>}
      {result.sourceQuote && (
        <p className="mt-2 border-l-2 border-zinc-700 pl-3 text-xs italic text-zinc-500">
          “{result.sourceQuote}”{result.sourcePage ? ` (p.${result.sourcePage})` : ""}
        </p>
      )}
      <button
        onClick={advance}
        className="mt-4 w-full rounded-lg bg-zinc-100 px-5 py-3 font-semibold text-zinc-900 hover:bg-white"
      >
        Continue →
      </button>
    </motion.div>
  );
}

function ResultScreen() {
  const phase = useCombat((s) => s.phase);
  const player = useCombat((s) => s.player);
  const summary = useCombat((s) => s.runSummary);
  const game = useCombat((s) => s.game);
  const start = useCombat((s) => s.start);
  const win = phase === "victory";

  useEffect(() => {
    if (win) sfx.victory();
    else sfx.defeat();
  }, [win]);

  // Server-authoritative meta (M5.3); fall back to in-memory player if the finish call failed.
  const score = summary?.score ?? player.score;
  const xp = summary?.xp ?? player.xp;
  const level = summary?.level ?? player.level;
  const insightEarned = summary?.insightEarned ?? 0;
  const insightTotal = summary?.insightTotal;
  const newly = summary?.newlyUnlocked ?? [];
  const mastery = Object.entries(summary?.masteryByTopic ?? {}).sort(
    (a, b) => b[1].accuracy - a[1].accuracy,
  );
  const isBest = summary?.isNewBest === true; // server decides (folds this run into bestScore)

  return (
    <div className="mx-auto flex w-full max-w-lg flex-1 flex-col items-center justify-center gap-5 px-5 py-10 text-center">
      <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}>
        <div className="text-5xl">{win ? "🏆" : "💀"}</div>
        <h1 className={`mt-3 text-3xl font-extrabold ${win ? "text-amber-300" : "text-rose-300"}`}>
          {win ? "Campaign Cleared!" : "Run Over"}
        </h1>
        <p className="mt-3 text-zinc-300">
          Score {score} · XP {xp} · Level {level}
        </p>
        {isBest && <p className="mt-1 text-sm font-semibold text-amber-300">🏅 New personal best!</p>}
      </motion.div>

      {summary != null ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="w-full rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5 text-left"
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sky-300">🔮 Insight earned</span>
            <span className="text-lg font-bold text-sky-200">+{insightEarned}</span>
          </div>
          {insightTotal != null && (
            <p className="mt-0.5 text-xs text-zinc-500">{insightTotal} total banked</p>
          )}

          {mastery.length > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-xs uppercase tracking-wide text-zinc-500">Topic mastery</p>
              <div className="flex flex-col gap-2">
                {mastery.map(([topic, m]) => (
                  <div key={topic} className="flex items-center gap-3">
                    <span className="w-32 shrink-0 truncate text-sm text-zinc-300" title={topic}>
                      {topic}
                    </span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-800">
                      <div
                        className={`h-full ${m.accuracy >= 0.8 ? "bg-emerald-500" : "bg-amber-500"}`}
                        style={{ width: `${Math.round(m.accuracy * 100)}%` }}
                      />
                    </div>
                    <span className="w-10 shrink-0 text-right text-xs text-zinc-400">
                      {Math.round(m.accuracy * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {newly.length > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-xs uppercase tracking-wide text-zinc-500">Relics unlocked</p>
              <div className="flex flex-wrap gap-1.5">
                {newly.map((r) => (
                  <span
                    key={r.relicId}
                    title={r.description}
                    className="flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-200"
                  >
                    <span>{r.icon}</span>
                    {r.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          <p className="mt-4 border-t border-zinc-800 pt-3 text-xs italic text-zinc-500">
            Insight rewards what you learned, not how long you played. Relics never answer for you.
          </p>
        </motion.div>
      ) : (
        <p className="text-sm text-zinc-400">Your progress was saved.</p>
      )}

      <div className="flex justify-center gap-3">
        {game && (
          <button
            onClick={() => start(game.campaignId)}
            className="rounded-lg bg-amber-500 px-5 py-3 font-semibold text-zinc-950 hover:bg-amber-400"
          >
            New run
          </button>
        )}
        <Link
          href="/"
          className="rounded-lg border border-zinc-700 px-5 py-3 text-zinc-200 hover:bg-zinc-800"
        >
          Home
        </Link>
      </div>
    </div>
  );
}
