"""One narrated MP4 per part of a screenshot set.

    python3 tools/screenshots/build_videos.py docs/screenshots/<set> [--voice Rishi]

Reads <set>/index.json (from capture.mjs) and <set>/narration.json:
  {"voice": "Rishi", "rate": 170, "pad": 1.2,
   "parts": [{"slug": "part-a-…", "intro": "Part A. …", "from": 1, "to": 10, "lines": {"1": "…", …}}]}
Each shot shows for the length of its spoken line (macOS `say`) plus `pad` seconds; ffmpeg muxes.
"""
import json, subprocess, shutil, sys, tempfile
from pathlib import Path

args = sys.argv[1:]
if not args:
    sys.exit(__doc__)
SET = Path(args[0]).resolve()
narr = json.loads((SET / "narration.json").read_text())
voice = args[args.index("--voice") + 1] if "--voice" in args else narr.get("voice", "Samantha")
rate, pad = str(narr.get("rate", 170)), float(narr.get("pad", 1.2))
index = {e["n"]: e["file"] for e in json.loads((SET / "index.json").read_text())}
OUT = SET / "video"; OUT.mkdir(exist_ok=True)
WORK = Path(tempfile.mkdtemp(prefix="shots-video-"))

def speak(text, path):
    subprocess.run(["say", "-v", voice, "-r", rate, "-o", str(path), "--data-format=LEI16@44100", text], check=True)
def duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).decode().strip())

for part in narr["parts"]:
    w = WORK / part["slug"]; w.mkdir()
    clips = []
    speak(part["intro"], w / "intro.wav")
    clips.append((SET / index[part["from"]], w / "intro.wav", duration(w / "intro.wav") + 0.6))
    for n in range(part["from"], part["to"] + 1):
        audio = w / f"{n:02d}.wav"; speak(part["lines"][str(n)], audio)
        clips.append((SET / index[n], audio, duration(audio) + pad))
    with (w / "frames.txt").open("w") as f:
        for img, _, secs in clips:
            f.write(f"file '{img}'\nduration {secs:.3f}\n")
        f.write(f"file '{clips[-1][0]}'\n")
    with (w / "audio.txt").open("w") as f:
        for i, (_, audio, secs) in enumerate(clips):
            padded = w / f"p{i:02d}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(audio), "-af", f"apad=whole_dur={secs:.3f}", str(padded)], check=True)
            f.write(f"file '{padded}'\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(w / "audio.txt"), "-c", "copy", str(w / "voice.wav")], check=True)
    out = OUT / f"{part['slug']}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(w / "frames.txt"), "-i", str(w / "voice.wav"),
                    "-vf", "scale=1440:900,format=yuv420p", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    print(f"{out.name}: {len(clips) - 1} steps, {sum(c[2] for c in clips):.0f}s, {out.stat().st_size / 1e6:.1f} MB")
shutil.rmtree(WORK, ignore_errors=True)
print(f"voice {voice} → {OUT}")
