"use client";

import { motion } from "motion/react";

import { useCombat } from "@/lib/combatStore";
import type { MapNode } from "@/lib/types";

import { PlayerHud } from "./HpBar";

const ICON: Record<string, string> = { battle: "⚔️", rest: "🏕️", boss: "💀" };

export default function MapView() {
  const game = useCombat((s) => s.game);
  const actIndex = useCombat((s) => s.actIndex);
  const player = useCombat((s) => s.player);
  const clearedNodeIds = useCombat((s) => s.clearedNodeIds);
  const reachable = useCombat((s) => s.reachable());
  const selectNode = useCombat((s) => s.selectNode);
  const lastRestHeal = useCombat((s) => s.lastRestHeal);
  const totalActs = useCombat((s) => s.totalActs());

  const act = game?.acts[actIndex];
  if (!act) return null;

  const cleared = new Set(clearedNodeIds);
  const reachableIds = new Set(reachable.map((n) => n.nodeId));

  const rows = new Map<number, MapNode[]>();
  for (const n of act.map.nodes) {
    const arr = rows.get(n.row) ?? [];
    arr.push(n);
    rows.set(n.row, arr);
  }
  const rowKeys = [...rows.keys()].sort((a, b) => a - b);

  return (
    <div className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-4 px-5 py-8 text-zinc-100">
      <PlayerHud player={player} />
      <div className="text-center text-xs uppercase tracking-widest text-zinc-500">
        {act.title} · Act {actIndex + 1}/{totalActs} · choose your path
      </div>
      {lastRestHeal ? (
        <p className="text-center text-sm text-emerald-300">Rested · +{lastRestHeal} HP</p>
      ) : null}

      <div className="flex flex-col gap-3">
        {rowKeys.map((rk) => (
          <div key={rk} className="flex justify-center gap-3">
            {(rows.get(rk) ?? []).map((n) => (
              <NodeCard
                key={n.nodeId}
                node={n}
                cleared={cleared.has(n.nodeId)}
                reachable={reachableIds.has(n.nodeId)}
                onPick={() => selectNode(n.nodeId)}
              />
            ))}
          </div>
        ))}
      </div>

      {reachable.length === 0 && (
        <p className="text-center text-xs text-zinc-600">No moves available.</p>
      )}
    </div>
  );
}

function NodeCard({
  node,
  cleared,
  reachable,
  onPick,
}: {
  node: MapNode;
  cleared: boolean;
  reachable: boolean;
  onPick: () => void;
}) {
  const base =
    "flex w-40 flex-col items-center gap-1 rounded-xl border px-3 py-3 text-center transition-colors";
  const state = cleared
    ? "border-zinc-800 bg-zinc-900/40 text-zinc-600"
    : reachable
      ? "border-amber-500/70 bg-zinc-900 text-zinc-100 hover:bg-zinc-800 cursor-pointer shadow-[0_0_18px_-6px_rgba(245,158,11,0.6)]"
      : "border-zinc-800 bg-zinc-900/40 text-zinc-600";

  const content = (
    <>
      <span className="text-xl">{cleared ? "✓" : (ICON[node.type] ?? "•")}</span>
      <span className="text-xs font-medium">{node.title}</span>
      {node.type === "boss" && !cleared && (
        <span className="rounded bg-rose-500/20 px-1.5 text-[10px] uppercase text-rose-300">
          boss
        </span>
      )}
    </>
  );

  if (reachable && !cleared) {
    return (
      <motion.button
        whileTap={{ scale: 0.97 }}
        onClick={onPick}
        className={`${base} ${state}`}
      >
        {content}
      </motion.button>
    );
  }
  return <div className={`${base} ${state}`}>{content}</div>;
}
