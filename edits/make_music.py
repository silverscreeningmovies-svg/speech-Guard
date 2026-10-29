"""Synthesise an original royalty-free hype bed for the cricket reel.

No samples, no licences: every sound here is generated from maths.
- kick / snare / hats / crash from sine + shaped noise
- bass from a filtered saw stack on an Am-F-C-G loop
- a reverse-noise riser + crash landing exactly on each bat-on-ball contact

Writes edits/music_bed.wav at 48kHz stereo.
"""
import numpy as np
import wave

SR = 48000
BPM = 96.0
BEAT = 60.0 / BPM          # 0.625s
BAR = BEAT * 4             # 2.5s
DUR = 19.4                 # matches the reel
N = int(DUR * SR)
rng = np.random.default_rng(7)

# verified contact times in the reel (absolute seconds)
CONTACTS = [1.36, 4.06, 7.10, 9.93, 12.75, 14.80, 17.86]

# Am - F - C - G  (frequencies in Hz, bass octave)
CHORDS = [
    (55.00, [220.00, 261.63, 329.63]),   # Am
    (43.65, [174.61, 220.00, 261.63]),   # F
    (65.41, [261.63, 329.63, 392.00]),   # C
    (49.00, [196.00, 246.94, 293.66]),   # G
]

mix = np.zeros((N, 2), dtype=np.float64)


def add(sig, t, pan=0.0, gain=1.0):
    """Mix a mono signal in at time t with constant-power pan (-1..1)."""
    i = int(t * SR)
    if i >= N:
        return
    n = min(len(sig), N - i)
    l = np.cos((pan + 1) * np.pi / 4)
    r = np.sin((pan + 1) * np.pi / 4)
    mix[i:i + n, 0] += sig[:n] * gain * l
    mix[i:i + n, 1] += sig[:n] * gain * r


def env(n, attack=0.002, decay=0.15, curve=3.0):
    a = max(1, int(attack * SR))
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    d = np.exp(-np.linspace(0, curve, n)) * np.linspace(1, 0, n) ** 0.25
    return e * d


def kick(dur=0.34, f0=120.0, f1=45.0, curve=7.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    # pitch drops from f0 to f1 -- classic 808 thump
    f = f1 + (f0 - f1) * np.exp(-t * 26)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR)
    click = rng.normal(0, 1, n) * np.exp(-t * 220) * 0.35
    return (body * np.exp(-t * curve) + click) * 0.9


def snare(dur=0.22):
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.normal(0, 1, n)
    # cheap one-pole high-pass so it sits above the bass
    hp = np.empty(n)
    prev_in = prev_out = 0.0
    for i in range(n):
        prev_out = 0.86 * (prev_out + noise[i] - prev_in)
        prev_in = noise[i]
        hp[i] = prev_out
    tone = np.sin(2 * np.pi * 190 * t) * 0.5
    return (hp * np.exp(-t * 20) + tone * np.exp(-t * 30)) * 0.55


def hat(dur=0.06, bright=0.9):
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.normal(0, 1, n)
    hp = np.diff(np.concatenate([[0.0], noise]))  # crude differentiator = brighter
    return hp * np.exp(-t * 90) * bright * 0.22


def crash(dur=1.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.normal(0, 1, n)
    hp = np.diff(np.concatenate([[0.0], noise]))
    shimmer = np.sin(2 * np.pi * 3200 * t) * 0.15
    return (hp * 0.5 + shimmer) * np.exp(-t * 3.2) * 0.4


def riser(dur=0.55):
    """Reverse-noise swell that lands on a downbeat."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.normal(0, 1, n)
    hp = np.diff(np.concatenate([[0.0], noise]))
    ramp = (np.linspace(0, 1, n) ** 2.2)
    return hp * ramp * 0.16


def saw(freq, dur, detune=0.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = freq * (1 + detune)
    ph = (f * t) % 1.0
    return (2 * ph - 1).astype(np.float64)


def bass_note(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = saw(freq, dur) * 0.6 + saw(freq, dur, 0.004) * 0.4
    # simple low-pass: moving average = removes the harsh top
    k = 24
    s = np.convolve(s, np.ones(k) / k, mode="same")
    e = np.minimum(1, t / 0.01) * np.exp(-t * 2.4)
    return s * e * 0.5


def pluck(freq, dur=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * freq * t) * 0.6 +
         np.sin(2 * np.pi * freq * 2 * t) * 0.25 +
         np.sin(2 * np.pi * freq * 3 * t) * 0.12)
    return s * np.exp(-t * 5.5) * 0.20


def pad(freqs, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for f in freqs:
        s += saw(f, dur, 0.0) + saw(f, dur, 0.003)
    s /= (len(freqs) * 2)
    k = 200
    s = np.convolve(s, np.ones(k) / k, mode="same")
    e = np.minimum(1, t / 0.35) * np.minimum(1, (dur - t) / 0.4)
    return s * e * 0.10


# ---- drums -------------------------------------------------------------
# kick pattern (in beats) -- pushes on 1, syncopated lift before 3 and 4
KICK = [0.0, 0.75, 2.5, 3.25]
bars = int(np.ceil(DUR / BAR))
for b in range(bars):
    t0 = b * BAR
    for k in KICK:
        add(kick(), t0 + k * BEAT, gain=1.0)
    # backbeat
    for s in (1.0, 3.0):
        add(snare(), t0 + s * BEAT, pan=0.05, gain=0.9)
    # hats: 8ths, with a 16th double on the last beat of every other bar
    for h in np.arange(0, 4, 0.5):
        add(hat(bright=0.5 if h % 1 else 0.9), t0 + h * BEAT, pan=0.35, gain=0.75)
    if b % 2 == 1:
        for h in np.arange(3.5, 4.0, 0.25):
            add(hat(bright=0.7), t0 + h * BEAT, pan=0.3, gain=0.6)

# ---- harmony -----------------------------------------------------------
for b in range(bars):
    t0 = b * BAR
    root, triad = CHORDS[b % 4]
    add(pad(triad, BAR * 0.98), t0, gain=1.0)
    # bass: root on 1, octave-ish push on 2.5, root on 3.5
    for off, mult in ((0.0, 1.0), (1.5, 1.0), (2.5, 2.0), (3.5, 1.0)):
        add(bass_note(root * mult, BEAT * 0.9), t0 + off * BEAT, gain=0.85)
    # sparse pluck melody, pentatonic
    if b % 2 == 0:
        add(pluck(triad[2] * 2), t0 + 1.75 * BEAT, pan=-0.25)
        add(pluck(triad[1] * 2), t0 + 3.0 * BEAT, pan=0.25)

# ---- action sync: riser into each hit, crash on it ---------------------
for c in CONTACTS:
    add(riser(0.55), c - 0.55, gain=1.0)
    add(crash(), c, gain=0.85)

# ---- master ------------------------------------------------------------
# gentle bus compression so the bed stays even under the bat sounds
env_abs = np.abs(mix).max(axis=1)
win = int(0.05 * SR)
kern = np.ones(win) / win
rms = np.sqrt(np.convolve(env_abs ** 2, kern, mode="same"))
gain = np.clip(0.42 / (rms + 1e-6), 0.35, 1.0)
mix *= gain[:, None]

# fades: 0.03s in, 0.9s out
fi = int(0.03 * SR)
fo = int(0.9 * SR)
mix[:fi] *= np.linspace(0, 1, fi)[:, None]
mix[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5

mix = np.tanh(mix * 1.15)                      # soft clip, keeps peaks musical
mix /= max(1.0, np.abs(mix).max() / 0.92)

pcm = (mix * 32767).astype(np.int16)
with wave.open("edits/music_bed.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("wrote edits/music_bed.wav", pcm.shape, f"{DUR}s")
