---
name: process-issues
description: "Work the team's issue tracker (issues/app.py — testers file issues there with screenshots) by launching the Issue Agent (.claude/agents/issue-agent.md) in its own context: it triages every customer report in intake onto a shared internal issue (attach / promote / ask / detach), pulls every New / Open issue, investigates each with the disciplined pipelines (/fix-issue, /find-issues, /address-feedback), and writes the verdict back with tools/issues_cli.py — status plus root cause, fix, tests added, recommended human testing, duplicate-of or spec reference — so the board updates itself. Triggers on: process issues, work the issue board, pick up new issues, tracker, <PREFIX>-nnn, what did the testers file, issue board, unprocessed issues, customer reports, intake, triage."
metadata:
  author: "Solo Product Toolkit"
  version: "3.0"
  category: "engineering"
---

# Process Issues — launch the Issue Agent

The tracker is a standalone app in `issues/`. Every verdict on it comes from the **Issue
Agent** (`.claude/agents/issue-agent.md`, role `agent`), which runs in its own context so
screenshots, reproductions and fixes never fill this session. This skill only launches it,
relays what it found and carries the owner's decisions back. The procedure, the status
machine and the rules live in the agent definition — do not work issues here.

## Procedure

1. **Check the board is up.** `eval "$(python3 tools/factory.py env)"`, then
   `python3 tools/issues_cli.py list` and `python3 tools/issues_cli.py intake` (customer
   reports waiting for triage, or flagged answered / reopened). Unreachable → say so and stop.
   Both empty → say so and stop; no agent to launch.
2. **Launch one Issue Agent** (Agent tool, `subagent_type: issue-agent`) for the whole
   queue. Pass along anything the user named: specific keys or report refs
   (`acme/ACME-501`), a module, a deployed `ISSUES_URL`. Otherwise its brief is "triage
   intake, then work every New and Open issue".
3. **Relay its report** to the user: the triage lines (each report → attached / promoted /
   asked / detached), one line per issue (key, old → new status, the human test to run),
   then any split or reopen recommendations and owner decisions it raised. A reopen
   recommendation is a tester's move on the internal board, never the agent's.
4. **Carry decisions back.** When the owner approves a split or answers a decision, resume
   the same agent (SendMessage to it) with that answer — the split, any triage change and
   any new verdict are the agent's moves, never this session's.
5. **Commit only when asked**; the message lists every key and what changed.
