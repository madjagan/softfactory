# softfactory

**From idea to a product that keeps evolving — every change proposed with evidence,
approved by you.**

A spec-first development framework for Claude Code. It interviews you to turn an idea
into a product summary, builds the repo from it, and then runs the
**discover → setup → develop → deploy → evolve** loop: feedback from real testers comes
in through the tracker, Claude investigates and proposes a verdict or a dated amendment
to the spec, and you decide. Nothing ships past a red gate, nothing on the board is
closed by Claude, and every change to a requirement is a dated entry in the ledger — so
the product evolves, and you can always see why.

What's inside: the skills, agents, hooks, templates and a lean issue tracker, kept
honest by a documents-as-ledger discipline.

Extracted from a production project (see `METHODOLOGY_BRIEF.md` for the methodology
and the evidence behind it) and generalized: every project-specific value lives in one
manifest, `factory.yaml`, which every skill, agent, hook and tool reads.

## The loop

```
 DISCOVER  /product-interview  CLI interview → personas · value proposition canvas (jobs, pains, gains → fit)
                            · component tools · alternatives · success metrics · stack → docs/PRODUCT_SUMMARY.md
     │
 SETUP     /setup-project  product summary → factory.yaml · PRD · plan · issues log · feature list
                            · human test plan · testing companion · CLAUDE.md · tracker · gates proven
     │
 DEVELOP   /create-feature  dated requirement → RED acceptance test → risk review → build → GREEN + real flow → log
           /fix-issue       describe → reproduce → root cause (file:line) → minimal fix → regression test → no regression → log
           /find-issues     hypotheses → case enumeration → layered tests with teeth → verdicts (never fixes)
     │
 DEPLOY    /release         tree identified → every gate green → deploy → smoke (health, asset type, version, login) → release log
     │
 EVOLVE    /address-feedback  clarify → classify from evidence → dispatch one skill → close the register honestly
           /process-issues    Issue Agent (own context): tracker queue → screenshots → skills → verdict + human test steps (never closes)
           /test-pack         human test plan · exploratory charters · per-module coaching pack, derived from the feature list
           /test-guide        a one-page customer tester's guide for one module / feature / use case, labels verified in the source
           /guide-screenshots annotated screenshot storyboard for a guide (ring + pointer + caption), narrated videos on request
           /issues-dashboard  classify the issues log → Issue Ledger page at a stable URL
           /marketing-site    the product's home page, derived from the ledger and the design system, at a stable URL
           docs-agent          answers "what does the product do"; owns and reconciles the per-persona user guides
           evaluator-assistant sits beside a human tester: expected behaviour, defect / by design / not built / UX finding
     │
     └──► evidence from testers and users → dated PRD amendment → you approve → back to DEVELOP
```

## Install into a project

```bash
git clone <this repo> softfactory
./softfactory/install.sh /path/to/your/repo
cd /path/to/your/repo
claude          # then:  /product-interview   (writes docs/PRODUCT_SUMMARY.md)
                #        /setup-project       (reads it; or pass a summary or a path to one)
```

`install.sh` copies the factory-owned files (`.claude/skills`, `.claude/agents`,
`.claude/hooks`, `tools/`, `issues/`, `templates/`) and writes the project-owned ones
once (`factory.yaml`, `CLAUDE.md`, `docs/*`). Re-run with `--update` to refresh the
framework without touching your ledger. `/product-interview` writes the product summary;
`/setup-project` then fills the manifest and the ledger from it, proves the verify and deploy gates, and starts the tracker.

## What is in here

| Path | What | Owner after install |
|---|---|---|
| `factory.example.yaml` | The manifest: name, stack, doc paths, commands per layer, personas, seed facts, tracker settings | project |
| `.claude/skills/*` | Thirteen gated pipelines (see the loop above). Same anatomy each: prime directive, principles, phases with gates, definition of done, anti-patterns | factory |
| `tools/screenshots/` | Storyboard capture for tester guides: `stack.sh` (fresh stack from the manifest), `lib.mjs` (ring + pointer + caption, shoot-then-click), `capture.mjs`, `build_videos.py`; `app.config.mjs` and `storyboards/` are the project's | factory + project |
| `.claude/agents/docs-agent.md` | Documentation authority; derives and reconciles user guides | factory |
| `.claude/agents/evaluator-assistant.md` | Assistant to a non-developer tester | factory |
| `.claude/agents/issue-agent.md` | The Issue Agent: works the tracker queue in its own context; the only actor that gives verdicts | factory |
| `.claude/hooks/` | Feature-list change detector (content hash) → asks for guide reconciliation; stale-citation checker | factory |
| `tools/factory.py` | Reads the manifest for scripts (`get`, `cmd`, `env`, `check`) | factory |
| `tools/issues_cli.py` | The Issue Agent's client for the tracker | factory |
| `tools/issues_dashboard.py` | Issues log → classified JSON → Issue Ledger HTML | factory |
| `tools/render_docs_site.py` | Internal docs site from the testing docs and the ledger | factory |
| `issues/` | The tracker: FastAPI + SQLite + screenshots, tester / agent / admin roles, server-enforced state machine, 1-n split of a report into parts (owner-approved), optional status-only customer board with mirroring | factory |
| `templates/` | CLAUDE.md, the docs ledger, CI workflow, classified JSON — filled by `/setup-project` | project |
| `deploy/docker-compose.issues.yml` | Two boards from one image, for internal deployments | project |

## The rules the framework enforces

1. **The ledger is the product's memory.** PRD, plan, issues log, feature list, release log. Work not recorded there did not happen.
2. **Every phase has a gate; the test is the definition of done; RED first.**
3. **Prove, never assume.** Root cause to `file:line` with a live observation; verify at the boundary that broke; drive the real flow.
4. **Classify from evidence against the written requirement**, not the reporter's words.
5. **One report, one class, one skill.**
6. **Minimal blast radius; sibling patterns; opt-in over global.**
7. **Derived artefacts are generated and drift-checked**, never hand-edited.
8. **Design seams for testability**: a clock seam, twin engines with parity tests, fresh seeds, guard tests. Third instance of a bug class → a guard test.
9. **Humans explore, automation checks.** Rule card, charters, report shape; every discovery returns as a test.
10. **Role separation on the board.** The Issue Agent proposes verdicts with human-test steps; humans verify and close; product decisions stay with the owner.
11. **Money, statutory and access changes are business decisions.** Confirm first.
12. **Real dates from the shell**; the app clock and the doc clock are never mixed.
13. **Write down the why**, tersely, everywhere.

## Developing the framework itself

```bash
python3 -m pytest issues/tests -q            # the tracker's state machine
python3 tools/factory.py --help
./install.sh /tmp/some-empty-dir && (cd /tmp/some-empty-dir && python3 tools/factory.py check)
```

Skills are Markdown; keep the anatomy (directive → principles → phases with gates → DoD →
anti-patterns) and reference manifest keys (`commands.verify`, `docs.prd`) rather than
project commands. A rule without its reason gets deleted by the next reader.
