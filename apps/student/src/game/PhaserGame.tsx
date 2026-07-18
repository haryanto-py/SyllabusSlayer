"use client";

import Phaser from "phaser";
import { useEffect, useRef } from "react";

import type { BattleSetup } from "./EventBus";
import { BattleScene, GAME_SIZE } from "./BattleScene";

// Client-only host: creates one Phaser.Game into a div and tears it down on unmount. Loaded via a
// dynamic({ ssr:false }) import (see BattleCanvas) so Phaser never runs on the server.
export default function PhaserGame({ setup }: { setup: BattleSetup }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<Phaser.Game | null>(null);
  // The game is created once at mount with the initial setup; later changes arrive via EventBus.
  const setupRef = useRef(setup);

  useEffect(() => {
    if (!parentRef.current || gameRef.current) return;
    const scene = new BattleScene();
    scene.pendingSetup = setupRef.current; // correct arena on the first frame, no setup flash
    gameRef.current = new Phaser.Game({
      type: Phaser.AUTO,
      parent: parentRef.current,
      width: GAME_SIZE.width,
      height: GAME_SIZE.height,
      transparent: true,
      scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
      audio: { noAudio: true },
      banner: false,
      scene,
    });
    return () => {
      gameRef.current?.destroy(true);
      gameRef.current = null;
    };
  }, []);

  return <div ref={parentRef} className="h-full w-full" />;
}
