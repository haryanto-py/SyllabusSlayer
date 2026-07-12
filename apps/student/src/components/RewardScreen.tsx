"use client";

import { AnimatePresence, motion } from "motion/react";

import { useCombat } from "@/lib/combatStore";

const RARITY: Record<string, string> = {
  rare: "border-amber-500/70 text-amber-300",
  uncommon: "border-sky-500/60 text-sky-300",
  common: "border-zinc-600 text-zinc-300",
};

export default function RewardScreen() {
  const options = useCombat((s) => s.rewardOptions);
  const choose = useCombat((s) => s.chooseReward);
  const wasBoss = useCombat((s) => s.lastClearedBoss);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center gap-6 px-5 py-10 text-zinc-100">
      <div className="text-center">
        <div className="text-4xl">{wasBoss ? "👑" : "✨"}</div>
        <h2 className="mt-2 text-xl font-extrabold text-amber-300">
          {wasBoss ? "Boss down — claim a relic" : "Choose a relic"}
        </h2>
        <p className="mt-1 text-sm text-zinc-400">
          Relics amplify what you already know. They never answer for you.
        </p>
      </div>

      {options.length === 0 ? (
        <p className="text-sm text-zinc-500">Summoning rewards…</p>
      ) : (
        <div className="grid w-full gap-3 sm:grid-cols-3">
          <AnimatePresence>
            {options.map((r, i) => (
              <motion.button
                key={r.relicId}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => choose(r.relicId)}
                className={`flex flex-col items-center gap-2 rounded-2xl border bg-zinc-900/80 p-5 text-center transition-colors hover:bg-zinc-900 ${
                  RARITY[r.rarity] ?? RARITY.common
                }`}
              >
                <span className="text-4xl">{r.icon}</span>
                <span className="font-bold text-zinc-100">{r.name}</span>
                <span className="text-[10px] font-semibold uppercase tracking-wide">{r.rarity}</span>
                <span className="text-xs text-zinc-400">{r.description}</span>
              </motion.button>
            ))}
          </AnimatePresence>
        </div>
      )}

      <button
        onClick={() => choose(null)}
        className="text-sm text-zinc-500 transition-colors hover:text-zinc-300"
      >
        Skip reward →
      </button>
    </div>
  );
}
