// Procedural sound effects synthesized with the Web Audio API — zero audio files, so it ships on
// any box with no asset pipeline or licensing. SSR-safe (all browser access is guarded). The
// AudioContext + mute state live on `window` so the single instance is shared whether this module
// is pulled into the main bundle (DOM screens) or the lazy Phaser chunk (BattleScene).

interface Win {
  __ssAudioCtx?: AudioContext;
  AudioContext?: typeof AudioContext;
  webkitAudioContext?: typeof AudioContext;
  localStorage: Storage;
}

function win(): Win | null {
  return typeof window === "undefined" ? null : (window as unknown as Win);
}

function ctx(): AudioContext | null {
  const w = win();
  if (!w) return null;
  if (!w.__ssAudioCtx) {
    const AC = w.AudioContext ?? w.webkitAudioContext;
    if (!AC) return null;
    w.__ssAudioCtx = new AC();
  }
  const c = w.__ssAudioCtx;
  // Browsers start the context suspended until a user gesture; combat is click-driven so this
  // resumes on the first hit/pick.
  if (c.state === "suspended") c.resume().catch(() => {});
  return c;
}

const mutedListeners = new Set<() => void>();

/** Subscribe to mute changes (for useSyncExternalStore in the toggle UI). */
export function subscribeMuted(cb: () => void): () => void {
  mutedListeners.add(cb);
  return () => mutedListeners.delete(cb);
}

export function isMuted(): boolean {
  const w = win();
  return !!w && w.localStorage.getItem("ss-muted") === "1";
}

export function setMuted(v: boolean): void {
  win()?.localStorage.setItem("ss-muted", v ? "1" : "0");
  mutedListeners.forEach((cb) => cb());
}

export function toggleMuted(): boolean {
  const v = !isMuted();
  setMuted(v);
  return v;
}

interface ToneOpts {
  freq: number;
  freqEnd?: number;
  type?: OscillatorType;
  dur: number;
  vol?: number;
  delay?: number;
}

function tone(o: ToneOpts): void {
  const c = ctx();
  if (!c || isMuted()) return;
  const t0 = c.currentTime + (o.delay ?? 0);
  const osc = c.createOscillator();
  const gain = c.createGain();
  osc.type = o.type ?? "sine";
  osc.frequency.setValueAtTime(o.freq, t0);
  if (o.freqEnd) osc.frequency.exponentialRampToValueAtTime(Math.max(1, o.freqEnd), t0 + o.dur);
  const vol = o.vol ?? 0.14;
  gain.gain.setValueAtTime(0.0001, t0);
  gain.gain.exponentialRampToValueAtTime(vol, t0 + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, t0 + o.dur);
  osc.connect(gain).connect(c.destination);
  osc.start(t0);
  osc.stop(t0 + o.dur + 0.03);
}

function chord(freqs: number[], o: Omit<ToneOpts, "freq" | "delay">, stagger = 0): void {
  freqs.forEach((f, i) => tone({ ...o, freq: f, delay: i * stagger }));
}

// --- combat cues ----------------------------------------------------------- //
export function hit(streak = 1): void {
  tone({ freq: 340, freqEnd: 150, type: "square", dur: 0.11, vol: 0.11 });
  if (streak > 1) tone({ freq: 700 + streak * 45, type: "triangle", dur: 0.14, vol: 0.09, delay: 0.02 });
}

export function hurt(): void {
  tone({ freq: 190, freqEnd: 55, type: "sawtooth", dur: 0.22, vol: 0.14 });
}

export function slay(): void {
  tone({ freq: 130, freqEnd: 42, type: "sine", dur: 0.42, vol: 0.18 });
  chord([523, 659, 784], { type: "triangle", dur: 0.2, vol: 0.08 }, 0.06);
}

export function reward(): void {
  chord([659, 988], { type: "sine", dur: 0.24, vol: 0.1 }, 0.08);
}

export function heal(): void {
  chord([440, 660], { type: "sine", dur: 0.3, vol: 0.09 }, 0.1);
}

export function victory(): void {
  chord([523, 659, 784, 1047], { type: "triangle", dur: 0.34, vol: 0.1 }, 0.12);
}

export function defeat(): void {
  chord([392, 330, 262], { type: "sine", dur: 0.42, vol: 0.12 }, 0.18);
}
