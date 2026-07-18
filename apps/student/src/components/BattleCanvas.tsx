"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef } from "react";

import {
  BATTLE_ANSWER,
  type BattleAnswer,
  type BattleSetup,
  EventBus,
} from "@/game/EventBus";
import type { AnswerResult } from "@/lib/types";

// Phaser is heavy and client-only — load it lazily and never on the server.
const PhaserGame = dynamic(() => import("@/game/PhaserGame"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-zinc-900/50" />,
});

export const ENEMY_EMOJI: Record<string, string> = {
  minion: "👾",
  elite: "👺",
  boss: "🐉",
};

// Bridges the combat store to the Phaser arena. The scene reads the initial setup at construction
// (so the first frame is correct); each new answer is forwarded as a BATTLE_ANSWER event. Mounted
// per-encounter inside the Arena, so a fresh scene is set up each battle via `setup`.
export default function BattleCanvas({
  enemyName,
  enemyEmoji,
  enemyFrac,
  playerFrac,
  lastResult,
  streak,
}: {
  enemyName: string;
  enemyEmoji: string;
  enemyFrac: number;
  playerFrac: number;
  lastResult: AnswerResult | null;
  streak: number;
}) {
  const setup: BattleSetup = { enemyName, enemyEmoji, enemyFrac, playerFrac };

  // Fire a hit/hurt animation whenever a new answer resolves.
  const lastSeen = useRef<AnswerResult | null>(null);
  useEffect(() => {
    if (!lastResult || lastResult === lastSeen.current) return;
    lastSeen.current = lastResult;
    const payload: BattleAnswer = {
      correct: lastResult.isCorrect,
      damage: lastResult.damage,
      streak,
      enemyFrac,
      playerFrac,
    };
    EventBus.emit(BATTLE_ANSWER, payload);
  }, [lastResult, enemyFrac, playerFrac, streak]);

  return (
    <div className="w-full overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950 aspect-[7/3]">
      <PhaserGame setup={setup} />
    </div>
  );
}
