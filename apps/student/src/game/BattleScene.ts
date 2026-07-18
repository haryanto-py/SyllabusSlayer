// The Phaser battle arena: two combatants, HP bars, and juice on every answer. Procedural only
// (emoji + graphics + particles) so it ships with zero binary assets — swap in real sprites later
// by giving the combatants a texture instead of a Text glyph. This scene renders feedback; it
// never computes damage or correctness (the server does that; React feeds results via EventBus).
import Phaser from "phaser";

import {
  BATTLE_ANSWER,
  BATTLE_SETUP,
  type BattleAnswer,
  type BattleSetup,
  EventBus,
} from "./EventBus";
import * as sfx from "./sfx";

const GAME_W = 700;
const GAME_H = 300;
const BAR_W = 150;
const BAR_H = 12;

export class BattleScene extends Phaser.Scene {
  /** Initial setup handed in at construction so the arena is correct on the very first frame. */
  pendingSetup: BattleSetup | null = null;

  private hero!: Phaser.GameObjects.Text;
  private enemy!: Phaser.GameObjects.Text;
  private enemyName!: Phaser.GameObjects.Text;
  private enemyBar!: Phaser.GameObjects.Graphics;
  private heroBar!: Phaser.GameObjects.Graphics;

  private heroX = 0;
  private enemyX = 0;
  private midY = 0;
  private enemyFrac = 1;
  private heroFrac = 1;

  constructor() {
    super("BattleScene");
  }

  create() {
    this.heroX = GAME_W * 0.24;
    this.enemyX = GAME_W * 0.76;
    this.midY = GAME_H * 0.52;

    // backdrop + ground
    this.add.rectangle(0, 0, GAME_W, GAME_H, 0x0b0b12).setOrigin(0);
    this.add.rectangle(0, GAME_H - 52, GAME_W, 52, 0x15151f).setOrigin(0);

    // 8px white dot texture for particle bursts
    const g = this.make.graphics({ x: 0, y: 0 });
    g.fillStyle(0xffffff, 1).fillCircle(4, 4, 4);
    g.generateTexture("spark", 8, 8);
    g.destroy();

    // soft glows behind each combatant + slow ambient embers (atmosphere, drawn behind sprites)
    this.add.circle(this.heroX, this.midY, 62, 0x22c55e, 0.1).setBlendMode(Phaser.BlendModes.ADD);
    this.add.circle(this.enemyX, this.midY, 72, 0xef4444, 0.1).setBlendMode(Phaser.BlendModes.ADD);
    this.add.particles(0, 0, "spark", {
      x: { min: 0, max: GAME_W },
      y: GAME_H + 6,
      lifespan: 4200,
      speedY: { min: -12, max: -30 },
      scale: { start: 0.5, end: 0 },
      alpha: { start: 0.22, end: 0 },
      tint: 0x6366f1,
      frequency: 420,
      quantity: 1,
    });

    this.hero = this.add.text(this.heroX, this.midY, "🧙", { fontSize: "72px" }).setOrigin(0.5);
    this.enemy = this.add.text(this.enemyX, this.midY, "👾", { fontSize: "92px" }).setOrigin(0.5);
    this.enemyName = this.add
      .text(this.enemyX, this.midY - 82, "", { fontSize: "15px", color: "#e4e4e7", fontStyle: "bold" })
      .setOrigin(0.5);

    this.enemyBar = this.add.graphics();
    this.heroBar = this.add.graphics();

    // gentle idle bob so the arena feels alive
    this.tweens.add({ targets: this.enemy, y: this.midY - 8, duration: 1400, yoyo: true, repeat: -1, ease: "Sine.inOut" });
    this.tweens.add({ targets: this.hero, y: this.midY - 5, duration: 1600, yoyo: true, repeat: -1, ease: "Sine.inOut" });

    this.drawBars();

    EventBus.on(BATTLE_SETUP, this.onSetup);
    EventBus.on(BATTLE_ANSWER, this.onAnswer);
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
      EventBus.off(BATTLE_SETUP, this.onSetup);
      EventBus.off(BATTLE_ANSWER, this.onAnswer);
    });

    if (this.pendingSetup) this.applySetup(this.pendingSetup);
  }

  private onSetup = (p?: unknown) => this.applySetup(p as BattleSetup);
  private onAnswer = (p?: unknown) => {
    const a = p as BattleAnswer | undefined;
    if (!a) return;
    if (a.correct) this.playHit(a);
    else this.playHurt(a);
  };

  private applySetup(s?: BattleSetup) {
    if (!s) return;
    this.enemy.setText(s.enemyEmoji || "👾").setAlpha(1).setAngle(0).setScale(0.6);
    this.enemyName.setText(s.enemyName || "");
    this.enemyFrac = s.enemyFrac;
    this.heroFrac = s.playerFrac;
    this.drawBars();
    this.tweens.add({ targets: this.enemy, scale: 1, duration: 340, ease: "Back.out" });
  }

  // --- correct answer: hero strikes the enemy -------------------------------- //
  private playHit(a: BattleAnswer) {
    this.tweens.add({
      targets: this.hero,
      x: this.enemyX - 90,
      duration: 130,
      yoyo: true,
      ease: "Quad.out",
      onYoyo: () => this.impact(a),
    });
  }

  private impact(a: BattleAnswer) {
    const crit = a.streak > 1;
    this.hitStop();
    sfx.hit(a.streak);
    this.cameras.main.shake(180, Math.min(0.02, 0.006 + a.damage / 1500));
    this.flash(this.enemyX, this.midY, crit ? 0xf59e0b : 0xffffff);
    this.tweens.add({ targets: this.enemy, scaleX: 1.28, scaleY: 0.78, duration: 90, yoyo: true, ease: "Quad.out" });
    this.burst(this.enemyX, this.midY, crit ? 0xf59e0b : 0xffffff, crit ? 20 : 12);
    this.floatText(this.enemyX, this.midY - 30, `-${a.damage}`, crit ? "#f59e0b" : "#ffffff", crit);
    if (crit) this.floatText(this.enemyX + 34, this.midY - 66, `🔥x${a.streak}`, "#fbbf24", false);
    this.animateBar("enemy", a.enemyFrac);
    if (a.enemyFrac <= 0) this.slayEnemy();
  }

  // --- wrong answer: enemy strikes the hero ---------------------------------- //
  private playHurt(a: BattleAnswer) {
    this.tweens.add({
      targets: this.enemy,
      x: this.heroX + 90,
      duration: 150,
      yoyo: true,
      ease: "Quad.out",
      onYoyo: () => {
        sfx.hurt();
        this.cameras.main.shake(140, 0.008);
        this.flash(this.heroX, this.midY, 0xef4444);
        this.tweens.add({ targets: this.hero, x: this.heroX - 26, duration: 80, yoyo: true, ease: "Quad.out" });
        this.floatText(this.heroX, this.midY - 30, "hit!", "#ef4444", false);
      },
    });
    this.animateBar("hero", a.playerFrac);
  }

  private slayEnemy() {
    sfx.slay();
    this.burst(this.enemyX, this.midY, 0xf59e0b, 30);
    this.tweens.add({ targets: this.enemy, alpha: 0, scale: 1.7, angle: 25, duration: 460, ease: "Quad.out" });
  }

  /** Brief hit-stop: freeze tweens for a beat on impact so the hit reads as "chunky". */
  private hitStop(ms = 55) {
    this.tweens.timeScale = 0.02;
    window.setTimeout(() => {
      if (this.tweens) this.tweens.timeScale = 1;
    }, ms);
  }

  // --- helpers --------------------------------------------------------------- //
  private flash(x: number, y: number, color: number) {
    const c = this.add.circle(x, y, 52, color, 0.55).setBlendMode(Phaser.BlendModes.ADD);
    this.tweens.add({ targets: c, scale: 1.9, alpha: 0, duration: 230, ease: "Quad.out", onComplete: () => c.destroy() });
  }

  private burst(x: number, y: number, color: number, count: number) {
    const p = this.add.particles(x, y, "spark", {
      speed: { min: 70, max: 240 },
      lifespan: 460,
      scale: { start: 1.1, end: 0 },
      tint: color,
      emitting: false,
    });
    p.explode(count);
    this.time.delayedCall(700, () => p.destroy());
  }

  private floatText(x: number, y: number, text: string, color: string, big: boolean) {
    const t = this.add
      .text(x, y, text, { fontSize: big ? "34px" : "24px", color, fontStyle: "bold" })
      .setOrigin(0.5);
    this.tweens.add({ targets: t, y: y - 62, alpha: 0, duration: 900, ease: "Quad.out", onComplete: () => t.destroy() });
  }

  private animateBar(which: "enemy" | "hero", to: number) {
    const from = which === "enemy" ? this.enemyFrac : this.heroFrac;
    this.tweens.addCounter({
      from: from * 100,
      to: Math.max(0, Math.min(1, to)) * 100,
      duration: 350,
      ease: "Quad.out",
      onUpdate: (tw) => {
        const v = (tw.getValue() ?? 0) / 100;
        if (which === "enemy") this.enemyFrac = v;
        else this.heroFrac = v;
        this.drawBars();
      },
    });
  }

  private drawBars() {
    this.paintBar(this.enemyBar, this.enemyX - BAR_W / 2, this.midY - 64, this.enemyFrac, 0xef4444);
    this.paintBar(this.heroBar, this.heroX - BAR_W / 2, this.midY - 60, this.heroFrac, 0x22c55e);
  }

  private paintBar(g: Phaser.GameObjects.Graphics, x: number, y: number, frac: number, color: number) {
    g.clear();
    g.fillStyle(0x000000, 0.5).fillRoundedRect(x - 1, y - 1, BAR_W + 2, BAR_H + 2, 4);
    g.fillStyle(0x27272a, 1).fillRoundedRect(x, y, BAR_W, BAR_H, 3);
    const fw = Math.max(0, Math.min(1, frac)) * BAR_W;
    if (fw > 0) g.fillStyle(color, 1).fillRoundedRect(x, y, fw, BAR_H, 3);
  }
}

export const GAME_SIZE = { width: GAME_W, height: GAME_H };
