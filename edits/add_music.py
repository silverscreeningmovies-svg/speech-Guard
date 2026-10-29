"""Mix the synthesised music bed into the cricket reel.

Steps:
1. Measure each bat-on-ball contact in the rendered reel (50ms RMS windows).
2. Gain-match every scene so all seven hits land at the same level -- some
   source clips (jf, the second jh scene) are 5-7 dB quieter than the rest.
3. Duck the music under the clip audio with sidechain compression so the
   cracks stay on top, then normalise the finished mix.
"""
import sys
import os
import re
import subprocess

sys.path.insert(0, "edits")
import build_deliverables as B

FF = B.FF
OUT = "edits"
TARGET_HIT_DB = -9.0     # aim every bat-on-ball crack at this RMS burst
MAX_BOOST_DB = 7.0       # don't rescue hopeless clips into pure noise
MUSIC_GAIN = 0.55


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def measure_hits(reel):
    r = sh([FF, "-i", reel, "-af",
            "astats=metadata=1:reset=1:length=0.05,"
            "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
            "-f", "null", "-"])
    t = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stdout)]
    v = [float(x) for x in re.findall(r"RMS_level=(-?[0-9.]+|-inf)", r.stdout)]
    out = []
    for c in B.contact_times(B.SCENES):
        win = [b for a, b in zip(t, v) if c - 0.15 <= a <= c + 0.20]
        out.append(max(win) if win else -20.0)
    return out


def scene_starts():
    starts, acc = [], 0.0
    for _, a, b, _ in B.SCENES:
        starts.append(acc)
        acc += b - a
    return starts


def gain_expression():
    """Per-scene volume as one ffmpeg expression over t."""
    hits = measure_hits(f"{OUT}/cricket-highlights-v2-notrees.mp4")
    starts = scene_starts()
    gains = [min(MAX_BOOST_DB, TARGET_HIT_DB - h) for h in hits]
    parts = []
    for i, (s0, g) in enumerate(zip(starts, gains)):
        end = starts[i + 1] if i + 1 < len(starts) else 1e6
        parts.append(f"between(t,{s0:.3f},{end:.3f})*{10 ** (g / 20):.4f}")
    expr = parts[-1]
    for p in reversed(parts[:-1]):
        expr = f"{p}+{expr}"
    print("hit levels:", [round(h, 1) for h in hits])
    print("scene gains:", [f"{g:+.1f} dB" for g in gains])
    return f"volume='{expr}':eval=frame"


def mix(reel, out_name, label):
    fc = (
        "[0:a]asplit=2[orig0][sc];"
        f"[orig0]{gain_expression()}[orig];"
        f"[1:a]volume={MUSIC_GAIN},afade=t=in:st=0:d=0.25[mus];"
        "[mus][sc]sidechaincompress=threshold=0.030:ratio=10:attack=4:release=240"
        ":makeup=1:mode=downward[ducked];"
        "[orig][ducked]amix=inputs=2:duration=first:dropout_transition=0,"
        "loudnorm=I=-15:TP=-1.5:LRA=9[a]"
    )
    r = sh([FF, "-y", "-i", reel, "-i", f"{OUT}/music_bed.wav",
            "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", f"{OUT}/{out_name}"])
    print(f"[{label}] {out_name}", "ok" if r.returncode == 0 else "ERROR")
    if r.returncode != 0:
        print("\n".join(r.stderr.strip().splitlines()[-8:]))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    contacts = B.contact_times(B.SCENES)

    if not os.path.exists(f"{OUT}/cricket-highlights-six-text.mp4"):
        B.build_reel("cricket-highlights-six-text.mp4", B.SCENES, "sixtext",
                     ass_events=B.ass_six_events(contacts))
    if not os.path.exists(f"{OUT}/cricket-highlights-v2-notrees.mp4"):
        B.build_reel("cricket-highlights-v2-notrees.mp4", B.SCENES, "notrees")

    mix(f"{OUT}/cricket-highlights-six-text.mp4",
        "cricket-highlights-music.mp4", "music+text")
    mix(f"{OUT}/cricket-highlights-v2-notrees.mp4",
        "cricket-highlights-music-notext.mp4", "music-notext")
