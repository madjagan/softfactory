---
name: process-tickets
description: "Work the support desk (support/app.py — customers file tickets there from the page or the in-app widget) by launching the Support Agent (.claude/agents/support-agent.md) in its own context: it pulls every new / open ticket waiting for a draft, checks release, known issues, feature status, the user guides and the PRD, and writes cited DRAFT replies or internal escalation recommendations with tools/support_cli.py. Nothing reaches a customer until a support person sends it. On demand only — never scheduled. Triggers on: process tickets, draft support replies, work the support queue, support desk, SUP-nnn, what did customers ask, unanswered tickets."
metadata:
  author: "Solo Product Toolkit"
  version: "1.0"
  category: "support"
---

# Process Tickets — launch the Support Agent

The support desk is a standalone app in `support/`. Drafts on it come from the **Support
Agent** (`.claude/agents/support-agent.md`, role `agent`), which runs in its own context so
guides, logs and screenshots never fill this session. This skill only launches it and relays
what it found. The checks and the rules live in the agent definition — do not draft here.

Runs **on demand only**: when someone asks. No schedule, and the server never calls an agent.

## Procedure

1. **Check the desk is up.** `eval "$(python3 tools/factory.py env)"`, then
   `python3 tools/support_cli.py list`. Unreachable → say so and stop. Empty queue → say so
   and stop; no agent to launch.
2. **Launch one Support Agent** (Agent tool, `subagent_type: support-agent`) for the whole
   queue. Pass along anything the user named: specific keys, an org, a deployed `SUPPORT_URL`.
   Otherwise its brief is "draft every ticket waiting for a draft".
3. **Relay its report**: one line per ticket (key → draft / recommend-escalate / needs human),
   then what it could not decide. Remind the user that drafts wait on the support page for a
   person to check and **Send**, and that escalations are a person's move (Escalated + the
   internal issue key).
4. Never send, escalate or change a status from this session.
