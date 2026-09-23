#!/usr/bin/env python3
"""Issue-log dashboard: docs/issues_classified.json → docs/issues_dashboard.html.

    python3 tools/issues_dashboard.py            # render the page
    python3 tools/issues_dashboard.py --pending  # list log entries not yet classified

The classification lives in the JSON (one record per "## " entry of docs/issues_log.md, matched
by title). The /issues-dashboard skill classifies whatever --pending lists, then renders and
republishes to the URL stored under meta.artifact_url.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from factory import ROOT, manifest, doc_path  # noqa: E402

M = manifest()
PROJECT = M.get("project", {}).get("name", "Project")
LOG = doc_path("issues_log")
DATA = doc_path("issues_classified")
OUT = doc_path("issues_dashboard")

LABEL = {
    "integration-wiring": "Integration / wiring", "ui-display": "UI / display", "functional-logic": "Functional logic",
    "data-config": "Data / config", "tooling-infra": "Tooling / infra", "missing-validation": "Missing validation",
    "crash-robustness": "Crash / robustness", "authorization": "Authorization", "boundary-condition": "Boundary condition",
    "performance": "Performance", "not-applicable": "No defect",
    "wiring-plumbing": "Wiring / plumbing", "logic-correction": "Logic correction", "ui-change": "UI change",
    "new-mechanism": "New mechanism", "new-validation": "New validation", "data-config-change": "Data / config change",
    "defensive-handling": "Defensive handling", "refactor-consolidation": "Refactor / consolidation",
    "test-or-docs-only": "Test or docs only", "none": "No change",
}


def headers() -> list[str]:
    return [l[3:].strip() for l in LOG.read_text(encoding="utf-8").splitlines() if l.startswith("## ")]


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip())[:90]


def pending(data: dict) -> list[str]:
    seen = {norm(e["title"]) for e in data["entries"]}
    return [h for h in headers() if norm(h) not in seen]


def stats(entries: list[dict]) -> dict:
    bugs = [e for e in entries if e["kind"] == "bug"]
    feats = [e for e in entries if e["kind"] == "feature"]
    n = len(bugs)
    bucket = Counter(e["issue_bucket"] for e in bugs)
    fix = Counter(e["fix_kind"] for e in bugs)
    module = Counter(e["module"] for e in bugs)
    layer = Counter(e["layer"] for e in bugs)
    matrix: dict[str, Counter] = defaultdict(Counter)
    for e in bugs:
        matrix[e["issue_bucket"]][e["fix_kind"]] += 1
    parts = 6
    per = max(1, -(-len(entries) // parts))
    trend = []
    for k in range(parts):
        chunk = [e for e in entries[k * per:(k + 1) * per] if e["kind"] == "bug"]
        trend.append({"part": k + 1, "bugs": len(chunk), "buckets": Counter(e["issue_bucket"] for e in chunk)})
    return {
        "n_entries": len(entries), "n_bugs": n, "n_features": len(feats),
        "kinds": Counter(e["kind"] for e in entries),
        "bucket": bucket.most_common(), "fix": fix.most_common(), "module": module.most_common(),
        "layer": layer.most_common(),
        "tests": sum(1 for e in bugs if e.get("regression_test_added")),
        "feature_fix": Counter(e["fix_kind"] for e in feats).most_common(),
        "matrix": {b: dict(c) for b, c in matrix.items()},
        "trend": [{"part": t["part"], "bugs": t["bugs"], "buckets": dict(t["buckets"])} for t in trend],
    }


HTML = r"""<meta charset="utf-8"><title>__PROJECT__ Issue Ledger</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;1,9..144,500&family=Geist:wght@400;500;600&family=Azeret+Mono:wght@400;500&display=swap">
<style>
:root{--bg:#F6FAF8;--card:#FFFFFF;--s2:#EEF4F0;--bd:#DFE8E2;--bd2:#C4D2C9;--ink:#0B1F17;--t2:#2E463C;--t3:#5C7267;--t4:#8A9C93;
  --nav:#0A3D2F;--navDeep:#05291F;--ac:#317A28;--as:rgba(49,122,40,.09);--mint:#8DF87D;--gn:#067647;--am:#B54708;--rd:#B42318;
  --heat0:#EEF4F0;--heat1:#CFE6C9;--heat2:#9FCF97;--heat3:#67AE5E;--heat4:#317A28;--heat5:#1E5A1A;
  --sn:"Geist",system-ui,-apple-system,"Segoe UI",sans-serif;--sf:"Fraunces","Iowan Old Style",Georgia,serif;--mn:"Azeret Mono",ui-monospace,"SF Mono",Menlo,monospace;}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0B1A14;--card:#10251D;--s2:#173127;--bd:#24443A;--bd2:#3A5C50;--ink:#EAF3EE;--t2:#C6D8CE;--t3:#93AB9F;--t4:#6F887C;
  --nav:#EAF3EE;--navDeep:#0B1A14;--ac:#6FCF63;--as:rgba(111,207,99,.14);--heat0:#173127;--heat1:#1F4A34;--heat2:#2E6A45;--heat3:#3E8C55;--heat4:#6FCF63;--heat5:#9BE58F;}}
:root[data-theme="dark"]{--bg:#0B1A14;--card:#10251D;--s2:#173127;--bd:#24443A;--bd2:#3A5C50;--ink:#EAF3EE;--t2:#C6D8CE;--t3:#93AB9F;--t4:#6F887C;
  --nav:#EAF3EE;--navDeep:#0B1A14;--ac:#6FCF63;--as:rgba(111,207,99,.14);--heat0:#173127;--heat1:#1F4A34;--heat2:#2E6A45;--heat3:#3E8C55;--heat4:#6FCF63;--heat5:#9BE58F;}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--sn);font-size:14px;line-height:1.5;margin:0}
.wrap{max-width:1180px;margin:0 auto;padding:36px 28px 72px}
.eyebrow{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--t4)}
h1{font-family:var(--sf);font-weight:500;font-size:40px;letter-spacing:-.01em;margin:6px 0 4px;text-wrap:balance;line-height:1.1}
h1 em{font-style:italic;color:var(--ac)}
.lede{color:var(--t3);max-width:62ch;margin:0}
.mono,.num{font-family:var(--mn);font-variant-numeric:tabular-nums}
.vitals{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:28px 0 8px}
.vital{padding:14px 16px;border-top:2px solid var(--ac);background:transparent}
.vital .v{font-family:var(--sf);font-size:32px;font-weight:500;line-height:1;letter-spacing:-.01em}
.vital .l{color:var(--t3);font-size:12px;margin-top:6px}
.vital.warn{border-top-color:var(--am)} .vital.warn .v{color:var(--am)}
h2{font-family:var(--sn);font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--t3);margin:0 0 12px;display:flex;align-items:center;gap:10px}
h2 .n{font-family:var(--mn);font-weight:400;color:var(--t4);letter-spacing:0;text-transform:none}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:18px;margin-top:28px}
.panel{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:18px 20px}
.panel p.note{color:var(--t3);font-size:12.5px;margin:10px 0 0;max-width:60ch}
.bars{display:grid;grid-template-columns:max-content 1fr max-content;gap:6px 12px;align-items:center}
.bars .lbl{font-size:13px;color:var(--t2);white-space:nowrap}
.bars .trk{height:14px;background:var(--s2);border-radius:3px;position:relative;overflow:hidden}
.bars .fill{position:absolute;inset:0 auto 0 0;background:var(--ac);border-radius:0 3px 3px 0;min-width:2px}
.bars .val{font-size:12px;color:var(--t3);text-align:right;white-space:nowrap}
.bars .val b{color:var(--ink);font-weight:500}
.bars .row:hover .fill{background:var(--gn)}
.heat{border-collapse:separate;border-spacing:2px;font-size:12px;width:100%}
.heat th{font-weight:500;color:var(--t3);text-align:left;padding:4px 6px;font-size:11.5px}
.heat th.col{writing-mode:vertical-rl;transform:rotate(180deg);text-align:left;white-space:nowrap;height:118px;vertical-align:bottom;padding:0 0 6px}
.heat td{padding:0;height:30px;min-width:30px;border-radius:4px;text-align:center;color:var(--ink);position:relative}
.heat td.h0{background:var(--heat0);color:var(--t4)} .heat td.h1{background:var(--heat1)} .heat td.h2{background:var(--heat2)} .heat td.h3{background:var(--heat3)} .heat td.h4{background:var(--heat4);color:#fff} .heat td.h5{background:var(--heat5);color:#fff}
.heat td:hover{outline:2px solid var(--mint);outline-offset:-2px}
.small{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}
.sm{padding:10px 12px;border:1px solid var(--bd);border-radius:10px;background:var(--card)}
.sm .t{font-size:12px;color:var(--t2);font-weight:500;margin-bottom:6px}
.sm svg{width:100%;height:64px;display:block;overflow:visible}
.controls{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px;align-items:center}
.controls input,.controls select{font:inherit;font-size:13px;color:var(--ink);background:var(--card);border:1.5px solid var(--bd2);border-radius:8px;padding:7px 10px}
.controls input{min-width:240px;flex:1}
.controls input:focus,.controls select:focus{outline:2px solid var(--mint);outline-offset:1px;border-color:var(--ac)}
.tablewrap{overflow-x:auto;border:1px solid var(--bd);border-radius:14px;background:var(--card)}
table.list{border-collapse:collapse;width:100%;min-width:900px;font-size:13px}
table.list th{background:var(--nav);color:#fff;font-size:11px;letter-spacing:.06em;text-transform:uppercase;font-weight:600;text-align:left;padding:10px 12px;position:sticky;top:0}
:root[data-theme="dark"] table.list th{color:var(--navDeep)}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) table.list th{color:var(--navDeep)}}
table.list td{padding:8px 12px;border-top:1px solid var(--bd);vertical-align:top}
table.list tr:hover td{background:var(--s2)}
.chip{display:inline-block;font-size:11px;padding:2px 9px;border-radius:20px;border:1px solid;white-space:nowrap}
.chip.bug{color:var(--rd);border-color:rgba(180,35,24,.35);background:rgba(180,35,24,.07)}
.chip.feature{color:var(--ac);border-color:rgba(49,122,40,.35);background:var(--as)}
.chip.diagnostic{color:var(--am);border-color:rgba(181,71,8,.35);background:rgba(181,71,8,.07)}
.chip.other,.chip.docs{color:var(--t3);border-color:var(--bd2);background:var(--s2)}
.tip{position:fixed;pointer-events:none;background:var(--navDeep);color:#EAF3EE;font-size:12px;padding:6px 9px;border-radius:8px;border:1px solid var(--bd2);opacity:0;transform:translate(-50%,-120%);transition:opacity .12s;z-index:9;white-space:nowrap}
.tip.on{opacity:1}
footer{margin-top:36px;color:var(--t4);font-size:12px;display:flex;gap:16px;flex-wrap:wrap}
@media (prefers-reduced-motion: reduce){*{transition:none!important}}
</style>
<div class="wrap">
  <div class="eyebrow">__PROJECT__ · __LOG__</div>
  <h1>Issue <em>Ledger</em></h1>
  <p class="lede">Every entry in the project's issue log, classified by what was actually wrong and by what the fix was. Refreshed with <span class="mono">/issues-dashboard</span>; the taxonomy is in <span class="mono">docs/issues_classified.json</span>.</p>
  <div class="vitals" id="vitals"></div>
  <div class="grid">
    <section class="panel"><h2>What was wrong <span class="n" id="n-bug"></span></h2><div class="bars" id="bars-bucket"></div><p class="note">Primary nature of the root cause, bug entries only. Feature sections that also closed a defect are listed in the table with their bucket.</p></section>
    <section class="panel"><h2>What the fix was <span class="n" id="n-fix"></span></h2><div class="bars" id="bars-fix"></div><p class="note">Dominant edit per bug. Feature sections are almost all "new mechanism" and are shown separately below.</p></section>
    <section class="panel"><h2>Where the bugs were <span class="n" id="n-mod"></span></h2><div class="bars" id="bars-module"></div></section>
    <section class="panel"><h2>How features were built <span class="n" id="n-feat"></span></h2><div class="bars" id="bars-feat"></div></section>
  </div>
  <div class="grid">
    <section class="panel" style="grid-column:1/-1"><h2>Bucket × fix <span class="n">bugs only · rows are what was wrong, columns what was done</span></h2><div style="overflow-x:auto"><table class="heat" id="heat"></table></div><p class="note">A tight diagonal means the fix matched the cause. Off-diagonal cells are the expensive ones: a wiring or logic bug that needed a whole new mechanism.</p></section>
  </div>
  <div class="grid">
    <section class="panel" style="grid-column:1/-1"><h2>Over time <span class="n">the log in six chronological parts · bugs per part by bucket</span></h2><div class="small" id="trend"></div></section>
  </div>
  <section style="margin-top:28px">
    <h2>Every entry <span class="n" id="n-shown"></span></h2>
    <div class="controls">
      <input id="q" type="search" placeholder="Search title, id, note…" aria-label="Search entries">
      <select id="f-kind" aria-label="Kind"><option value="">All kinds</option></select>
      <select id="f-bucket" aria-label="Bucket"><option value="">All buckets</option></select>
      <select id="f-fix" aria-label="Fix kind"><option value="">All fix kinds</option></select>
      <select id="f-module" aria-label="Module"><option value="">All modules</option></select>
    </div>
    <div class="tablewrap"><table class="list"><thead><tr><th>Id</th><th>Title</th><th>Kind</th><th>What was wrong</th><th>What the fix was</th><th>Layer</th><th>Module</th><th>Test</th></tr></thead><tbody id="rows"></tbody></table></div>
  </section>
  <footer><span>Generated __DATE__</span><span>__NENT__ entries classified of __NHDR__ in the log</span><span>Taxonomy v__TAX__</span></footer>
</div>
<div class="tip" id="tip"></div>
<script>
const DATA = __DATA__;
const LABEL = __LABEL__;
const lab = (k) => LABEL[k] || k;
const $ = (s) => document.querySelector(s);
const tip = $('#tip');
function showTip(e, text){ tip.textContent = text; tip.style.left = e.clientX + 'px'; tip.style.top = e.clientY + 'px'; tip.classList.add('on'); }
function hideTip(){ tip.classList.remove('on'); }
const S = DATA.stats;
// vitals
const pend = DATA.pending;
$('#vitals').innerHTML = [
  ['Entries', S.n_entries, 'in the log'], ['Bug fixes', S.n_bugs, 'entries that fixed a defect'], ['Feature sections', S.n_features, '§ entries'],
  ['Regression tests', Math.round(100 * S.tests / Math.max(1, S.n_bugs)) + '%', S.tests + ' of ' + S.n_bugs + ' bugs added one'],
  [pend ? 'Unclassified' : 'Up to date', pend || '✓', pend ? 'new entries — run /issues-dashboard' : 'every log entry is classified'],
].map(([l, v, d], i) => `<div class="vital${i === 4 && pend ? ' warn' : ''}"><div class="v num">${v}</div><div class="l"><b>${l}</b> · ${d}</div></div>`).join('');
// bar lists
function bars(el, pairs, total){
  const max = Math.max(...pairs.map(p => p[1]));
  el.innerHTML = pairs.map(([k, v]) => `<div class="row" style="display:contents"><div class="lbl">${lab(k)}</div><div class="trk" data-t="${lab(k)}: ${v} (${(100*v/total).toFixed(1)}%)"><div class="fill" style="width:${100*v/max}%"></div></div><div class="val"><b>${v}</b> · ${(100*v/total).toFixed(0)}%</div></div>`).join('');
  el.querySelectorAll('.trk').forEach(t => { t.addEventListener('mousemove', (e) => showTip(e, t.dataset.t)); t.addEventListener('mouseleave', hideTip); });
}
bars($('#bars-bucket'), S.bucket, S.n_bugs); $('#n-bug').textContent = S.n_bugs + ' bugs';
bars($('#bars-fix'), S.fix, S.n_bugs); $('#n-fix').textContent = S.n_bugs + ' bugs';
bars($('#bars-module'), S.module.slice(0, 10), S.n_bugs); $('#n-mod').textContent = 'top 10 modules';
bars($('#bars-feat'), S.feature_fix, S.n_features); $('#n-feat').textContent = S.n_features + ' features';
// heat matrix
const fixCols = S.fix.map(p => p[0]);
const rowsB = S.bucket.map(p => p[0]);
const hmax = Math.max(...rowsB.flatMap(b => fixCols.map(f => (S.matrix[b] || {})[f] || 0)));
const cls = (v) => v === 0 ? 'h0' : 'h' + Math.min(5, Math.ceil(5 * v / hmax));
$('#heat').innerHTML = '<tr><th></th>' + fixCols.map(f => `<th class="col">${lab(f)}</th>`).join('') + '</tr>' +
  rowsB.map(b => `<tr><th>${lab(b)}</th>` + fixCols.map(f => { const v = (S.matrix[b] || {})[f] || 0; return `<td class="${cls(v)} num" data-t="${lab(b)} → ${lab(f)}: ${v}">${v || ''}</td>`; }).join('') + '</tr>').join('');
$('#heat').querySelectorAll('td').forEach(t => { t.addEventListener('mousemove', (e) => showTip(e, t.dataset.t)); t.addEventListener('mouseleave', hideTip); });
// trend small multiples: top buckets overall, one sparkbar per part
const topB = S.bucket.slice(0, 6).map(p => p[0]);
const tmax = Math.max(...topB.flatMap(b => S.trend.map(t => t.buckets[b] || 0)));
$('#trend').innerHTML = topB.map(b => {
  const vals = S.trend.map(t => t.buckets[b] || 0);
  const w = 100 / vals.length;
  const rects = vals.map((v, i) => { const h = tmax ? 56 * v / tmax : 0; return `<rect x="${(i * w + 1).toFixed(1)}%" width="${(w - 2).toFixed(1)}%" y="${(60 - h).toFixed(1)}" height="${h.toFixed(1)}" rx="2" fill="var(--ac)"><title>${lab(b)} · part ${i + 1}: ${v}</title></rect>`; }).join('');
  const labels = vals.map((v, i) => `<text x="${(i * w + w / 2).toFixed(1)}%" y="72" text-anchor="middle" font-size="9" fill="var(--t4)" font-family="Azeret Mono, monospace">${i + 1}</text>`).join('');
  return `<div class="sm"><div class="t">${lab(b)} <span class="num" style="color:var(--t4)">${vals.join(' · ')}</span></div><svg viewBox="0 0 100 76" preserveAspectRatio="none"><line x1="0" x2="100" y1="60" y2="60" stroke="var(--bd)" stroke-width=".6"/>${rects}${labels}</svg></div>`;
}).join('');
// table
const E = DATA.entries;
const fills = (sel, key) => { const c = {}; E.forEach(e => { c[e[key]] = (c[e[key]] || 0) + 1; }); Object.keys(c).sort().forEach(k => { const o = document.createElement('option'); o.value = k; o.textContent = `${lab(k)} (${c[k]})`; sel.appendChild(o); }); };
fills($('#f-kind'), 'kind'); fills($('#f-bucket'), 'issue_bucket'); fills($('#f-fix'), 'fix_kind'); fills($('#f-module'), 'module');
function render(){
  const q = $('#q').value.trim().toLowerCase();
  const fk = $('#f-kind').value, fb = $('#f-bucket').value, ff = $('#f-fix').value, fm = $('#f-module').value;
  const shown = E.filter(e => (!fk || e.kind === fk) && (!fb || e.issue_bucket === fb) && (!ff || e.fix_kind === ff) && (!fm || e.module === fm)
    && (!q || `${e.id} ${e.title} ${e.note || ''}`.toLowerCase().includes(q)));
  $('#rows').innerHTML = shown.map(e => `<tr><td class="num">${e.id}</td><td>${e.title}<div style="color:var(--t4);font-size:12px">${e.note || ''}</div></td><td><span class="chip ${e.kind}">${e.kind}</span></td><td>${lab(e.issue_bucket)}</td><td>${lab(e.fix_kind)}</td><td>${e.layer}</td><td>${e.module}</td><td>${e.regression_test_added ? '✓' : ''}</td></tr>`).join('');
  $('#n-shown').textContent = shown.length + ' of ' + E.length;
}
['#q', '#f-kind', '#f-bucket', '#f-fix', '#f-module'].forEach(s => $(s).addEventListener('input', render));
render();
</script>
"""


def render(data: dict) -> str:
    entries = data["entries"]
    s = stats(entries)
    payload = {"stats": s, "entries": entries, "pending": len(pending(data))}
    html = (HTML.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
            .replace("__LABEL__", json.dumps(LABEL))
            .replace("__PROJECT__", PROJECT).replace("__LOG__", str(LOG.relative_to(ROOT)))
            .replace("__DATE__", date.today().isoformat())
            .replace("__NENT__", str(len(entries))).replace("__NHDR__", str(len(headers())))
            .replace("__TAX__", str(data["meta"].get("taxonomy_version", 1))))
    return html


def main(argv: list[str]) -> int:
    data = load()
    if "--pending" in argv:
        p = pending(data)
        print("\n".join(p) if p else "(nothing pending — every log entry is classified)")
        return 0
    OUT.write_text(render(data), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} — {len(data['entries'])} entries, {len(pending(data))} pending")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
