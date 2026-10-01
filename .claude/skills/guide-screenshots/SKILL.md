---
name: guide-screenshots
description: "Given a tester's guide (docs/<SUBJECT>_TEST_GUIDE.md), produce its annotated screenshot storyboard — one shot per step with a red ring, a pointer and a numbered caption, captured on a fresh local test stack — and, on request, one narrated video per part. Triggers on: screenshots for the guide, capture the steps, storyboard, walkthrough images, narrated video, user help video, /guide-screenshots."
metadata:
  author: "softfactory"
  version: "1.0"
  category: "documentation"
---

# Guide screenshots — a storyboard for one tester's guide

The argument is the guide: `docs/<SUBJECT>_TEST_GUIDE.md` (written by `/test-guide`). The
output is `docs/screenshots/<subject>/`: numbered PNGs, `index.json`, a `README.md`
storyboard, and — only when asked — `narration.json` and `video/*.mp4`.
`tools/screenshots/storyboards/example-payroll.mjs` is the storyboard shape to copy.

## The tooling (all under `tools/screenshots/`)

- `app.config.mjs` — **project-owned**: base URL, API URL, demo password, sign-in selectors,
  sidebar group selectors, the API login shape. Written once by `install.sh`; `/setup-project`
  fills it. If a selector here is stale, every storyboard times out on step one — fix it first.
- `stack.sh up|down` — a FRESH test seed, the API on its own port with test-only tools
  enabled, a dev server proxying to it. The commands come from `factory.yaml →
  screenshots.{seed, api, web, api_health, web_url}`. Never the developer's own backend,
  never the deployed site: the guide's destructive steps run for real here.
- `lib.mjs` — `Capture`: `login(email, {shotSignIn})`, `group(gid)` / `adminGroup(gid,
  captions)` for the sidebar, `shot(locator, caption, {click, file, wait})` which draws the
  ring + pointer + numbered caption, screenshots, clears, then clicks. `api(email)` for SETUP
  writes.
- `capture.mjs <storyboard>` — runs `storyboards/<name>.mjs`, writes `index.json` + `README.md`.
- `build_videos.py <set> [--voice …]` — one MP4 per part from `narration.json` (macOS `say` +
  ffmpeg; on another OS, substitute the TTS call in the script's `speak()`).
- `vite.shots.config.mjs` — for Vite projects, the dev server with its API proxy repointed.

Needs: `playwright` installed in the repo (`npm i -D playwright && npx playwright install chromium`).

## Procedure

1. **Read the guide** and list its numbered steps per part. Each step becomes one `shot`. A
   step whose result is worth seeing (a status chip, a list, a file) becomes two: the click,
   then the result with `click: false` or a bare `shot(null, caption, {file})`.
2. **Find each target in the UI source — never guess:** `getByRole('button', {name})` on the
   rendered label (regex when the label carries a count or a version), `aria-label` /
   `data-testid` where the page has them, `getByText(..., {exact: true})` inside a sidebar
   group container. Tabs and the main action can share a label — use `.last()` / `.first()`
   deliberately and say why in a comment.
3. **Write the storyboard** `tools/screenshots/storyboards/<subject>.mjs`: `title`, `guide`,
   `outDir`, `setup(api)` for the state the guide assumes (idempotent; a 409 is fine), and
   `parts[]` — one per login, each `{title, login, shotSignIn?, run(cap, page)}` in the
   guide's order. Captions are the guide's step text, trimmed; the number is added by the
   library.
4. **Run it:** `tools/screenshots/stack.sh up` → `node tools/screenshots/capture.mjs
   <subject>` → `stack.sh down`. A selector that times out is a wrong label or a hidden
   control: fix the storyboard (or the guide, if the guide was wrong) and rerun from the top —
   setup makes reruns idempotent, numbering restarts. The stack shares the test database with
   the backend suite: never run both at once.
5. **Look at the shots** (Read three or four: the first, a mid-flow state, the last). The ring
   must sit on the control the caption names, the caption must not cover it, and the page
   state must be the step's. A wrong state usually means a missing `wait`.
6. **Report:** the count, the folder, the README. Offer the videos in one line.
7. **Videos, only when asked:** write `<set>/narration.json` — `voice`, `rate`, `pad`, and per
   part `slug`, `intro`, `from`, `to`, `lines` keyed by shot number. Lines are a spoken rewrite
   of the guide's steps (what to press, what to expect), not the captions read aloud; ≤ 25
   words each. `python3 tools/screenshots/build_videos.py docs/screenshots/<subject> --voice
   <name>`. Check one MP4 with ffprobe (h264 + aac, the configured viewport) and its mean
   volume (speech ≈ −17 dB).

## Conventions

- Viewport and ring colour from `app.config.mjs` (default 1440×900, `#D92D20`); captions
  prefixed with the shot number.
- File names `NN-<caption-slug>.png`; the sign-in shot is `NN-sign-in.png`.
- One part per login; the sign-in is shot once, for the role the guide is about.
- The storyboard never edits data by hand: state comes from the fresh seed plus `setup(api)`.
- Commit the PNGs, `index.json`, `README.md` and the storyboard; videos and `narration.json`
  only when the owner wants them in the repo.
- When the capture contradicts the guide (a label, an order, a rule), **fix the guide** and
  say so — the capture is the ground truth.

## Anti-patterns

- Capturing on the deployed site (real testers' data) or against the developer's backend.
- Labels from the guide or the PRD instead of the rendered source.
- Running the backend suite while a capture uses the test database.
- Building videos unasked, or reading captions as narration.
