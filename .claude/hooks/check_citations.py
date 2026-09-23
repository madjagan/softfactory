#!/usr/bin/env python3
"""Do the guides' `FEATURE_LIST.md:NNN` citations still point at their feature rows?

Any insertion into the feature list shifts every line below it, so citations rot silently —
nothing fails, the reader just lands on the wrong row. It has happened twice in one day.
Prints one line per stale citation; exits 1 if any are stale.
"""
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
sys.path.insert(0, str(root / "tools"))
try:
    from factory import doc_path  # the project manifest names the files
    src, guides = doc_path("feature_list"), doc_path("user_guides")
except Exception:  # no manifest yet: the conventional paths
    src = root / "docs" / "FEATURE_LIST.md"
    guides = root / "docs" / "user-guide"
if not src.exists() or not guides.is_dir():
    sys.exit(0)

loc: dict[str, int] = {}
for i, line in enumerate(src.read_text().splitlines(), 1):
    # Feature rows: **LVE-01**
    for m in re.finditer(r"\*\*([A-Z]{3}-\d\d)\*\*", line):
        loc.setdefault(m.group(1), i)
    # Gap rows: | D-9 | … — a different id shape, and the guides cite these too. Missing them
    # made this checker half-blind: it passed clean while §8.D-9's own citation was four lines
    # out.
    m = re.match(r"\|\s*([A-D]-\d+)\s*\|", line)
    if m:
        loc.setdefault(m.group(1), i)

pat = re.compile(r"((?:[A-Z]{3}-\d\d)|(?:[A-D]-\d+))[^\n]{0,80}?FEATURE_LIST\.md:(\d+)")
stale = []
for f in sorted(guides.glob("*.md")):
    for m in pat.finditer(f.read_text()):
        fid, cited = m.group(1), int(m.group(2))
        actual = loc.get(fid)
        if actual and actual != cited:
            stale.append(f"{f.name}: {fid} cites :{cited}, actually at :{actual}")

for s in stale:
    print(s)
sys.exit(1 if stale else 0)
