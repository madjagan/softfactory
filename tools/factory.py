#!/usr/bin/env python3
"""The project manifest (factory.yaml) for scripts and skills.

    python3 tools/factory.py get commands.verify      # one value, for shell use
    python3 tools/factory.py cmd verify               # run a manifest command, exit with its status
    python3 tools/factory.py env                      # export lines for the issue tracker
    python3 tools/factory.py check                    # every referenced doc exists, commands are set

Reads PyYAML when installed; otherwise a small parser for the subset the template uses
(nested maps, scalars, inline and block lists). Paths resolve against the repo root.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("FACTORY_ROOT") or Path(__file__).resolve().parents[1])
MANIFEST = ROOT / "factory.yaml"

# Conventional locations; the manifest's docs: block overrides any of them.
DEFAULT_DOCS = {
    "prd": "docs/PRODUCT_REQUIREMENTS.md",
    "plan": "docs/IMPLEMENTATION_PLAN.md",
    "issues_log": "docs/issues_log.md",
    "issues_classified": "docs/issues_classified.json",
    "issues_dashboard": "docs/issues_dashboard.html",
    "feature_list": "docs/FEATURE_LIST.md",
    "user_guides": "docs/user-guide",
    "why_testing": "docs/WHY_WE_NEED_TESTING.md",
    "testing_companion": "docs/TESTING_COMPANION.md",
    "test_plan_human": "docs/TEST_PLAN_HUMAN.md",
    "release_log": "docs/RELEASE_LOG.md",
    "seeding": "docs/SEEDING.md",
}


def _scalar(v: str):
    v = v.strip()
    if not v:
        return ""
    if v[0] in "\"'" and v[-1] == v[0]:
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in v[1:-1].split(",") if x.strip()]
    low = v.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def _parse(text: str) -> dict:
    """Indentation-driven parser for the manifest subset: maps, scalars, lists of scalars or maps."""
    lines = []
    for raw in text.splitlines():
        s = raw.split(" #", 1)[0] if not raw.lstrip().startswith("#") else ""
        if s.strip():
            lines.append((len(s) - len(s.lstrip()), s.strip()))
    root: dict = {}
    pos = 0

    def block(indent: int):
        nonlocal pos
        if pos < len(lines) and lines[pos][1].startswith("- "):
            return seq(indent)
        out: dict = {}
        while pos < len(lines):
            ind, s = lines[pos]
            if ind < indent:
                break
            if ind > indent:
                raise ValueError(f"bad indent near: {s}")
            key, _, val = s.partition(":")
            pos += 1
            if val.strip() in (">", "|", ">-", "|-"):  # block scalar: the indented lines below
                parts = []
                while pos < len(lines) and lines[pos][0] > indent:
                    parts.append(lines[pos][1]); pos += 1
                out[key.strip()] = ("\n" if val.strip().startswith("|") else " ").join(parts)
            elif val.strip():
                out[key.strip()] = _scalar(val)
            elif pos < len(lines) and lines[pos][0] > indent:
                out[key.strip()] = block(lines[pos][0])
            else:
                out[key.strip()] = None
        return out

    def seq(indent: int):
        nonlocal pos
        out: list = []
        while pos < len(lines) and lines[pos][0] == indent and lines[pos][1].startswith("- "):
            ind, s = lines[pos]
            body = s[2:].strip()
            pos += 1
            if ":" in body and not body.startswith(("[", "\"", "'")):
                # a map item: "- key: value" with more keys on following lines
                sub_indent = indent + 2
                lines.insert(pos, (sub_indent, body))
                out.append(block(sub_indent))
            else:
                out.append(_scalar(body))
        return out

    root = block(lines[0][0] if lines else 0)
    return root


def manifest() -> dict:
    if not MANIFEST.exists():
        return {}
    text = MANIFEST.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        return _parse(text)


def get(path: str, default=None):
    cur: object = manifest()
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def doc_path(key: str) -> Path:
    rel = get(f"docs.{key}") or DEFAULT_DOCS.get(key) or f"docs/{key}"
    return ROOT / rel


def cmd(name: str) -> int:
    c = get(f"commands.{name}")
    if not c:
        print(f"factory.yaml has no commands.{name}", file=sys.stderr)
        return 2
    print(f"$ {c}", file=sys.stderr)
    return subprocess.call(c, shell=True, cwd=ROOT)


def env_lines() -> list[str]:
    m = manifest()
    iss = m.get("issues", {}) or {}
    proj = m.get("project", {}) or {}
    out = {
        "ISSUES_URL": iss.get("url", "http://127.0.0.1:3002"),
        "ISSUES_PREFIX": iss.get("prefix", "IS"),
        "ISSUES_BRAND": iss.get("brand") or f"{proj.get('name', 'Project')} · issues",
        "ISSUES_MODULES": ",".join(iss.get("modules") or []),
        "ISSUES_PUSH_ACTOR": iss.get("push_actor") or proj.get("name", "Product team"),
    }
    return [f"export {k}={shlex.quote(str(v))}" for k, v in out.items() if v]


def check() -> int:
    m = manifest()
    rc = 0
    if not m:
        print("no factory.yaml at repo root — run /setup-project")
        return 1
    for key in ("name", "slug", "summary"):
        if not (m.get("project") or {}).get(key):
            print(f"project.{key} missing"); rc = 1
    for key in ("verify", "test_unit", "deploy"):
        if not (m.get("commands") or {}).get(key):
            print(f"commands.{key} missing"); rc = 1
    for key in DEFAULT_DOCS:
        if key == "issues_dashboard":  # generated by tools/issues_dashboard.py
            continue
        p = doc_path(key)
        if not p.exists():
            print(f"docs.{key}: {p.relative_to(ROOT)} does not exist"); rc = 1
    print("manifest ok" if rc == 0 else "manifest has gaps")
    return rc


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__); return 0
    if argv[0] == "get":
        v = get(argv[1])
        print(json.dumps(v) if isinstance(v, (dict, list)) else ("" if v is None else v)); return 0
    if argv[0] == "cmd":
        return cmd(argv[1])
    if argv[0] == "env":
        print("\n".join(env_lines())); return 0
    if argv[0] == "check":
        return check()
    if argv[0] == "dump":
        print(json.dumps(manifest(), indent=2)); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
