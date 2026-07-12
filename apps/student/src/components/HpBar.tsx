"use client";

import { motion } from "motion/react";

export function HpBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div className="h-3 w-full overflow-hidden rounded-full bg-zinc-800">
      <motion.div
        className={`h-full ${color}`}
        animate={{ width: `${pct}%` }}
        transition={{ type: "spring", stiffness: 120, damping: 20 }}
      />
    </div>
  );
}

export interface PlayerStats {
  hp: number;
  maxHp: number;
  streak: number;
  xp: number;
  level: number;
  score: number;
}

export function PlayerHud({ player }: { player: PlayerStats }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
      <div className="mb-2 flex items-center justify-between text-sm text-zinc-300">
        <span>
          ❤️ {player.hp}/{player.maxHp}
        </span>
        <span className="flex gap-3">
          <span className="text-amber-300">🔥 {player.streak}</span>
          <span>Lv {player.level}</span>
          <span>XP {player.xp}</span>
          <span>⚔️ {player.score}</span>
        </span>
      </div>
      <HpBar value={player.hp} max={player.maxHp} color="bg-emerald-500" />
    </div>
  );
}
