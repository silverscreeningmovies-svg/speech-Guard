# Cricket clips — edit deliverables

Source clips: Google Drive folder **"clips cricket"** (5 handheld vertical mp4s).
Downloads land in `google_drive/` (gitignored); renders land in `edits/` (video gitignored,
scripts committed).

## How the cuts were found
1. Scanned each clip's audio for transient peaks (`astats` RMS in 0.2s windows).
2. Verified every candidate on a contact sheet — several loud peaks were talking or
   wind, not bat-on-ball, and were dropped.
3. Cut `[contact - ~2s, contact + ~1.5s]` so each shot has run-up in and follow-through out.

Verified contacts: `yyu` 7.36 / 16.20, `iygiyu` 4.16, `lk` 1.23, `jf` 3.23,
`jh` 4.06 / 8.52.

## Outputs (all in `edits/`)

| File | Length | What it is |
|---|---|---|
| `cricket-highlights-v2-notrees.mp4` | 19.4s | 7 verified hits, trees footage removed, 720x1280 |
| `cricket-highlights-six-text.mp4` | 19.4s | Same reel, animated "SIX!" burst on each contact |
| `best-hit-slowmo.mp4` | 5.3s | Best hit (`lk`) at 0.4x, motion-interpolated to 60fps |
| `slowmo-combo.mp4` | 8.4s | Normal speed hit, then the same hit at 0.4x |
| `all-five-clean.mp4` | 86.5s | All five clips full length, no trims, normalised |
| `square-1x1-insta.mp4` | 19.4s | 1080x1080 Instagram feed export |
| `wide-16x9-yt.mp4` | 19.4s | 1920x1080 YouTube export, blurred pillarbox |

`cricket-highlights-v1.mp4` is the earlier 6-hit draft (kept for reference).

## Rebuild

```bash
pip install --break-system-packages imageio-ffmpeg
python3 edits/build_deliverables.py
```

Known constraint: this ffmpeg build is compiled **without** `drawtext`/freetype, so all
burnt-in text is generated as `.ass` subtitles and rendered with the `ass` filter
(gives the scale-pop animation and clean outlines). Fades, loudness (`-16 LUFS`),
and speed changes are all in `build_deliverables.py`.

## Notes for future passes
- `iygiyu` past ~8s is dead footage (camera whips to trees) — never use it.
- `yyu`'s loud peaks at 27s+ are people talking, not hits.
- Sources are 360x640 except `lk` (536x954); everything is upscaled to 720x1280,
  so `lk` is the sharpest shot in the reel.
