// Alert sound (B-60): one AudioContext per page, created by a user gesture; 880 Hz, gain 0.25, 0.5 s.
let audio: AudioContext | null = null;

export function beep(): void {
  if (!audio) return;
  const o = audio.createOscillator(), g = audio.createGain();
  o.frequency.value = 880; g.gain.value = 0.25;
  o.connect(g).connect(audio.destination);
  o.start(); o.stop(audio.currentTime + 0.5);
}

/** Arm (or re-test): must run inside a click handler. Plays the test beep. */
export function arm(): void {
  audio ??= new AudioContext();
  void audio.resume();
  beep();
}
