---
name: process-ideas
description: "Work the ideas portal (ideas/app.py — customers submit and vote there, staff log what they heard) by launching the Ideas Agent (.claude/agents/ideas-agent.md) in its own context: it gathers portal intake, tracker feature / enhancement / as_speced issues and (when the support desk exists) feature-request tickets, attaches or promotes each, drafts the public text, recommends decisions, applies in_development / shipped from the ledger with citations, and drafts notices on shipped — then relays what waits for the owner. On demand only. Triggers on: process ideas, feature requests, idea portal, what are customers asking for, IDEA-nn, IDR-nn, demand for a feature, sync ideas with the ledger, who asked for this."
metadata:
  author: "Solo Product Toolkit"
  version: "1.0"
  category: "product"
---

# Process Ideas — launch the Ideas Agent

The portal is a standalone app in `ideas/`. Linking, drafting and ledger sync come from the
**Ideas Agent** (`.claude/agents/ideas-agent.md`, role `agent`), in its own context. This
skill launches it, relays its report and carries the owner's decisions back. It runs **on
demand only**: no schedule, and the server never calls an agent.

## Procedure

1. **Check the portal is up.** `eval "$(python3 tools/factory.py env)"`, then
   `python3 tools/ideas_cli.py intake`. Unreachable → say so and stop.
2. **Launch one Ideas Agent** (Agent tool, `subagent_type: ideas-agent`). Pass along what the
   user named (keys, an org, a deployed `IDEAS_URL`). Otherwise its brief is "gather, triage,
   sync the ledger, draft notices". Tell it whether the support source is on: only when
   `support/` and `tools/support_cli.py` exist.
3. **Relay its report**: links made, statuses applied with citations, then **awaiting
   product** (accept / decline / already built / merge / publish) and drafts waiting to be
   sent.
4. **Carry the owner's decisions.** These are the owner's calls, made in chat:
   - **Accept:** run `/create-feature` for the idea; then record the section it produced:
     `python3 tools/ideas_cli.py accept IDEA-n --prd 3.14 [--feature AREA-NN]` (product role).
   - **Decline / already built / merge / publish / send:** on the product view of the page,
     signed in as product. A declined published idea needs the reason customers will see.
   Resume the same agent (SendMessage) only for agent work that follows from a decision
   (redrafting public text, a new link).
5. **Commit only when asked.**
