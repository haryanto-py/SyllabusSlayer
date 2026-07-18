// Minimal event bus bridging React and the Phaser battle scene. Deliberately Phaser-free so it
// is SSR-safe and never drags Phaser into the server bundle. React emits; the scene listens and
// animates. Phaser is purely presentational — it never decides combat outcomes.
type Handler = (payload?: unknown) => void;

class EventBusImpl {
  private handlers = new Map<string, Set<Handler>>();

  on(event: string, handler: Handler): () => void {
    const set = this.handlers.get(event) ?? new Set<Handler>();
    set.add(handler);
    this.handlers.set(event, set);
    return () => this.off(event, handler);
  }

  off(event: string, handler: Handler): void {
    this.handlers.get(event)?.delete(handler);
  }

  emit(event: string, payload?: unknown): void {
    // copy to a snapshot so a handler that unsubscribes mid-emit can't mutate the live set
    [...(this.handlers.get(event) ?? [])].forEach((h) => h(payload));
  }
}

export const EventBus = new EventBusImpl();

export const BATTLE_SETUP = "battle:setup";
export const BATTLE_ANSWER = "battle:answer";

/** Configure the arena for a (new) encounter. Fractions are 0..1. */
export interface BattleSetup {
  enemyName: string;
  enemyEmoji: string;
  enemyFrac: number;
  playerFrac: number;
}

/** Play the result of one answer. `*Frac` are the POST-resolution HP fractions (0..1). */
export interface BattleAnswer {
  correct: boolean;
  damage: number;
  streak: number;
  enemyFrac: number;
  playerFrac: number;
}
