"""Build every edit deliverable from the downloaded Drive clips.

Sources live in google_drive/ (gitignored). Outputs land in edits/.

Contact timestamps below came from an audio transient scan (RMS spikes), then
each one was verified frame-by-frame on a contact sheet before being used --
several loud peaks turned out to be talking, not bat-on-ball, and were dropped.

Text is rendered with libass (this ffmpeg build has no drawtext/freetype), so
"big text" bursts live in generated .ass files with a scale-pop animation.
"""
import imageio_ffmpeg
import subprocess
import os

FF = imageio_ffmpeg.get_ffmpeg_exe()
FONTDIR = "/usr/share/fonts/truetype/dejavu"
OUT = "edits"

# (file, in, out, contact_time)
# iygiyu only contributes 3.0-5.8s: past ~8s the camera whips away to the trees.
SCENES = [
    ("yyu",    6.00,  8.90,  7.36),
    ("iygiyu", 3.00,  5.80,  4.16),
    ("yyu",   14.80, 17.80, 16.20),
    ("lk",     0.00,  3.02,  1.23),
    ("jf",     2.20,  4.22,  3.23),
    ("jh",     3.00,  5.80,  4.06),
    ("jh",     7.20, 10.00,  8.52),
]

ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Six,DejaVu Sans,116,&H00FFFFFF,&H00FFFFFF,&H00000000,&H55000000,-1,0,0,0,100,100,2,0,1,7,3,5,0,0,0,1
Style: Tag,DejaVu Sans,26,&H00FFFFFF,&H00FFFFFF,&H00000000,&H55000000,-1,0,0,0,100,100,1,0,1,3,1,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ts(t):
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def ass_six_events(contacts, big_text="SIX!"):
    """Scale-pop + fade bursts pinned to each contact time."""
    ev = []
    for t0 in contacts:
        t1 = t0 + 1.15
        # pop from 145% -> 100% over 200ms, hold, fade out at the tail
        txt = (
            r"{\an5\pos(360,270)\fad(90,220)"
            r"\fscx145\fscy145\t(0,200,\fscx100\fscy100)}" + big_text
        )
        ev.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},Six,,0,0,0,,{txt}")
    return ev


def ass_tag_event(t0, t1, text, pos="(30,44)"):
    txt = r"{\an7\pos%s\fad(120,0)}%s" % (pos, text)
    return f"Dialogue: 1,{ts(t0)},{ts(t1)},Tag,,0,0,0,,{txt}"


def write_ass(path, events):
    with open(path, "w") as fh:
        fh.write(ASS_HEAD)
        fh.write("\n".join(events) + "\n")
    return path


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FAILED:", " ".join(cmd)[:300])
        print("\n".join(r.stderr.strip().splitlines()[-6:]))
    return r.returncode


def vfilter(i, a, b, w=720, h=1280):
    return (
        f"[{i}:v]trim={a}:{b},setpts=PTS-STARTPTS,"
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},fps=30,setsar=1,format=yuv420p[v{i}]"
    )


def encode(inputs, fc, vmap, amap, out_name, label, crf="20", extra=None):
    cmd = [FF, "-y", *inputs, "-filter_complex", fc, "-map", vmap, "-map", amap,
           "-c:v", "libx264", "-preset", "medium", "-crf", crf,
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
           "-movflags", "+faststart"]
    if extra:
        cmd += extra
    cmd.append(f"{OUT}/{out_name}")
    print(f"[{label}] {out_name}", "ok" if run(cmd) == 0 else "ERROR")


def build_reel(out_name, scenes, label, ass_events=None, dims=(720, 1280), crf="20"):
    inputs, chains, labels = [], [], []
    for i, (f, a, b, _) in enumerate(scenes):
        inputs += ["-i", f"google_drive/{f}.mp4"]
        chains.append(vfilter(i, a, b, *dims))
        chains.append(
            f"[{i}:a]atrim={a}:{b},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=0.06,afade=t=out:st={max(0, (b - a) - 0.10):.2f}:d=0.10,"
            f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]"
        )
        labels.append(f"[v{i}][a{i}]")
    fc = (";".join(chains) +
          f";{''.join(labels)}concat=n={len(scenes)}:v=1:a=1[vc][ac];"
          f"[ac]loudnorm=I=-16:TP=-1.5:LRA=11[ao]")
    vmap = "[vc]"
    if ass_events:
        ass = write_ass(f"{OUT}/_tmp_{label}.ass", ass_events)
        fc += (f";[vc]ass=filename={ass}:fontsdir={FONTDIR}[vt]")
        vmap = "[vt]"
    encode(inputs, fc, vmap, "[ao]", out_name, label, crf=crf)


def contact_times(scenes):
    out, acc = [], 0.0
    for f, a, b, c in scenes:
        out.append(acc + (c - a))
        acc += b - a
    return out


def total_len(scenes):
    return sum(b - a for _, a, b, _ in scenes)


def build_slowmo():
    """0.4x slow-motion replay of the best hit (lk -- closest framing, best res)."""
    a, b = 0.30, 2.45
    ass = write_ass(f"{OUT}/_tmp_slowmo.ass", [ass_tag_event(0.15, 99, "SLOW-MO 0.4x")])
    fc = (
        f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS,"
        f"scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,"
        f"minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
        f"setpts=2.5*PTS,ass=filename={ass}:fontsdir={FONTDIR}[v];"
        f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,atempo=0.5,atempo=0.8,aresample=48000[a]"
    )
    cmd = [FF, "-y", "-i", "google_drive/lk.mp4", "-filter_complex", fc,
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart",
           f"{OUT}/best-hit-slowmo.mp4"]
    print("[slowmo] best-hit-slowmo.mp4", "ok" if run(cmd) == 0 else "ERROR")


def build_combo():
    """Normal speed full clip, then the same hit replayed at 0.4x."""
    ass = write_ass(f"{OUT}/_tmp_combo.ass", [
        ass_tag_event(0.2, 3.02, "NORMAL SPEED"),
        ass_tag_event(3.2, 99, "REPLAY \\h0.4x"),
    ])
    fc = (
        "[0:v]trim=0:3.02,setpts=PTS-STARTPTS,"
        "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30,setsar=1[v1];"
        "[0:a]atrim=0:3.02,asetpts=PTS-STARTPTS,aresample=48000[a1];"
        "[0:v]trim=0.30:2.45,setpts=PTS-STARTPTS,"
        "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,"
        "minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,setpts=2.5*PTS[v2raw];"
        "[0:a]atrim=0.30:2.45,asetpts=PTS-STARTPTS,atempo=0.5,atempo=0.8,aresample=48000[a2];"
        "[v1][a1][v2raw][a2]concat=n=2:v=1:a=1[vc][a];"
        f"[vc]ass=filename={ass}:fontsdir={FONTDIR}[v]"
    )
    cmd = [FF, "-y", "-i", "google_drive/lk.mp4", "-filter_complex", fc,
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart",
           f"{OUT}/slowmo-combo.mp4"]
    print("[combo] slowmo-combo.mp4", "ok" if run(cmd) == 0 else "ERROR")


def build_all_clean():
    """All five source clips, full length, no trims, normalised framing + loudness."""
    files = ["yyu", "jh", "iygiyu", "jf", "lk"]
    inputs, chains, labels = [], [], []
    for i, f in enumerate(files):
        inputs += ["-i", f"google_drive/{f}.mp4"]
        chains.append(vfilter(i, 0, 9999))
        chains.append(
            f"[{i}:a]asetpts=PTS-STARTPTS,aresample=48000,"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]"
        )
        labels.append(f"[v{i}][a{i}]")
    fc = (";".join(chains) +
          f";{''.join(labels)}concat=n={len(files)}:v=1:a=1[vc][ac];"
          f"[ac]loudnorm=I=-16:TP=-1.5:LRA=11[ao]")
    encode(inputs, fc, "[vc]", "[ao]", "all-five-clean.mp4", "clean", crf="21")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    src = "edits/cricket-highlights-v2-notrees.mp4"

    # 1. trees-free reel (7 verified hits)
    contacts = contact_times(SCENES)
    build_reel("cricket-highlights-v2-notrees.mp4", SCENES, "notrees")

    # 2. same reel with "SIX!" bursts on every contact
    six = ass_six_events(contacts)
    build_reel("cricket-highlights-six-text.mp4", SCENES, "sixtext", ass_events=six)

    # 3 & 4. slow-mo replay of the best hit, and normal+slow combo
    build_slowmo()
    build_combo()

    # 5. all five clips joined clean
    build_all_clean()

    # 6. platform exports from the trees-free reel
    sq_ass = write_ass(f"{OUT}/_tmp_sq.ass", ass_six_events(contact_times(SCENES)))
    # re-time the SIX bursts for the 1:1 crop (same timeline, text repositioned per style)
    square_events = []
    for t0 in contact_times(SCENES):
        txt = (r"{\an5\pos(540,215)\fad(90,220)"
               r"\fscx145\fscy145\t(0,200,\fscx100\fscy100)}SIX!")
        square_events.append(f"Dialogue: 0,{ts(t0)},{ts(t0 + 1.15)},Six,,0,0,0,,{txt}")

    ass_sq = write_ass(f"{OUT}/_tmp_sq.ass", square_events)
    fc = (
        f"[0:v]scale=1920:1920:force_original_aspect_ratio=increase,crop=1920:1920,"
        f"scale=1080:1080,setsar=1,ass=filename={ass_sq}:fontsdir={FONTDIR}[v];"
        f"[0:a]anull[a]"
    )
    encode(["-i", src], fc, "[v]", "[a]", "square-1x1-insta.mp4", "square", crf="20")

    # 16:9 with blurred pillarbox so the whole vertical frame survives
    fc = (
        "[0:v]split[bgs][fgs];"
        "[bgs]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
        "boxblur=42:4,eq=brightness=-0.10[bg];"
        "[fgs]scale=-2:1080[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v];"
        "[0:a]anull[a]"
    )
    encode(["-i", src], fc, "[v]", "[a]", "wide-16x9-yt.mp4", "wide", crf="20")

    for f in os.listdir(OUT):
        if f.startswith("_tmp_") and f.endswith(".ass"):
            os.remove(os.path.join(OUT, f))
