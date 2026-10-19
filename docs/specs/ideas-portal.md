# Spec — lightweight feature-request portal (`ideas/`)

## Purpose

Customers and the team ask for new capabilities. The tool collects every request, wherever it comes
from, and groups requests for the same thing into one **idea**. It shows how much demand each idea
has, and lets customers vote on a **curated** version of the idea without seeing who else asked or
how they put it. An accepted idea becomes a dated PRD section through `/create-feature`. Its status
then follows the ledger until it ships, and everyone who asked for it hears about it.

It lives inside softfactory as a sibling of `issues/` and `support/`.

## Architecture (same pattern as `issues/` and `support/`)

| | Issue tracker | Support desk | Ideas portal |
|---|---|---|---|
| Process | FastAPI + SQLite + uploads | same | same |
| Page | one static `index.html` | customer + support views | portal view (customers) + product view (team) |
| Tenancy | internal + per-customer boards | one server, org tokens | **one server, org tokens** (as support) |
| Agent | Issue Agent | Support Agent | **Ideas Agent** (`.claude/agents/ideas-agent.md`), role `agent` |
| CLI | `issues_cli.py` | `support_cli.py` | `tools/ideas_cli.py` |
| Skill | `/process-issues` | `/process-tickets` | `/process-ideas`, on demand only |
| Config | `issues:` | `support:` | `ideas:` in `factory.yaml` |
| Deploy | compose | compose | `deploy/docker-compose.ideas.yml` |

## Concepts

- **Submission:** one request from one source, in the requester's own words. It is **private**: the
  submitting org, the product team and the agent can see it.
- **Idea:** the team's single statement of a capability, in the team's words. Many submissions link
  to one idea. Internal only, until it is published.
- **Published idea:** the curated public face of an idea (a public title and description, with no
  customer names or wording). Every customer can see it and vote on it.

## Sources (all four)

| Source | How it arrives | Ref kept |
|---|---|---|
| Portal | a customer submits on the portal page | `org`, requester |
| Support | a ticket the Support Agent categorises as a feature request. The agent recommends a link, and support confirms it | `SUP-1042` |
| Tracker | issues of kind `feature` / `enhancement`, and `as_speced` verdicts where the reporter wanted different behaviour | `IS-612` or `acme/ACME-501` |
| Internal | staff log what they heard on calls, in sales or in their own use | staff name, plus an optional org the request is on behalf of |

Support and tracker sources are linked by the **Ideas Agent through the CLIs** while
`/process-ideas` runs. There is no server-to-server sync, because ideas aren't time-critical.

## Goals and success criteria

| # | Criterion | Proved by |
|---|---|---|
| I1 | A customer submits an idea on the portal and sees only their own org's submissions | API test: org A cannot see org B's submissions (404) |
| I2 | Submissions from all four sources land in **intake** with their source ref | tests per source |
| I3 | The agent **attaches** a submission to an existing idea or **promotes** it to a new one. It can also recommend that an idea is **already built** (pointing at an `AREA-NN` that is ● in the feature list) or a **merge** of two ideas | tests |
| I4 | Demand per idea = distinct orgs, distinct people, votes, linked tickets and linked issues, shown in the product view and sortable | test |
| I5 | Only the product role **publishes** an idea, using the public title and description. The portal never shows a submission's text, requester or org on a published idea | customer-API test with a planted marker string |
| I6 | One vote per customer user per published idea. Voting again removes the vote. A customer sees the vote count but not who voted | tests |
| I7 | Only the product role **accepts** or **declines** an idea. Accepting it records the PRD § that `/create-feature` produced | server role test |
| I8 | After acceptance, status follows the ledger: plan row In progress → `in_development`; feature list ● and in `RELEASE_LOG.md` → `shipped`. The agent applies these during `/process-ideas` and cites the row | test with fixture ledger docs |
| I9 | On `shipped`, the agent drafts a notice for each linked submission (and a support draft for each linked ticket). Nothing reaches a customer until product sends it | tests: drafts not in the customer API until sent |
| I10 | Every move is in `history`, and the server enforces the state machine below | API tests per role |

## Roles

| Role | Who | May do |
|---|---|---|
| `customer` | portal users, by org token + name | submit; see own org's submissions; see and vote on published ideas |
| `product` | the product owner / team | everything: publish, accept, decline, merge, edit public text, send drafts, log internal submissions |
| `agent` | Ideas Agent, through the CLI | attach, promote, recommend (already built / merge / decline), draft public text and notices, apply **ledger-derived** statuses (`in_development`, `shipped`). It never accepts, declines, publishes or sends |
| `admin` | operator | anything |

## Idea states

```
            ┌──────── product ────────┐
new ──► under_review ──► accepted ──agent (plan row)──► in_development ──agent (● + released)──► shipped
              │                       
              ├──product──► declined          (public reason, if published)
              ├──product──► already_built     (→ AREA-NN; agent recommends)
              └──product──► merged            (→ other idea; submissions and votes move across)
```

- `new`: just promoted from a submission. `under_review`: the agent has linked it and drafted the
  public text.
- Accept, decline, already-built and merge are **product decisions**, following the house rule that
  business decisions are the owner's.
- `in_development` and `shipped` are **facts read from the ledger**, so the agent may set them. Each
  one cites the plan row or release entry it came from.
- Submission status, as the submitter sees it, is the status of its idea, mapped to plain words:
  received / under review / planned / in development / shipped / not planned / already available.

## Data model (one JSON doc per row, like issues)

```
submissions: { key: "IDR-2041", source: portal|support|tracker|internal, sourceRef, org, requester,
               text, screenshots, idea: null | "IDEA-88", createdAt, history }
ideas:       { key: "IDEA-88", title, problem, status, prdRef, featureId, mergedInto,
               submissions: [keys], public: null | {title, description, publishedAt, statusNote},
               drafts: [{to: submissionKey | ticketKey, text, sentAt}], history }
votes:       (idea, org, user) unique
```

Demand is computed on read from `submissions` and `votes`. It is never stored.

## Agent behaviour (`/process-ideas` → Ideas Agent, its own context, on demand)
1. **Gather:** portal intake; support tickets categorised as feature requests that aren't linked
   yet; tracker issues of kind feature or enhancement, and `as_speced` ones, that aren't linked yet.
   Create submissions for the last two.
2. **Triage each submission:** check the feature list first (● means already built → recommend
   `already_built`, citing `AREA-NN`; ◐ or a §8 gap means link it to the idea for that gap). Then
   look for an existing idea to attach to, and promote only when nothing matches.
3. **For new or changed ideas:** write the team's problem statement and draft the public title and
   description, with no customer wording or names.
4. **Ledger sync:** for each accepted idea, read the plan row for its `prdRef`, the feature list row
   for its `featureId`, and the release log. Apply `in_development` / `shipped` with a citation.
5. **On shipped:** draft notices for each submission, plus a support draft for each linked ticket.
6. **Report:** links made, recommendations awaiting product (accept / decline / already built /
   merge / publish), statuses applied, drafts waiting to be sent.

Accepting an idea is the owner's call in chat. The session then runs `/create-feature` and records
the PRD § on the idea with `ideas_cli.py accept IDEA-88 --prd 3.14`, using the product role. The
agent doesn't do this step itself.

## Configuration (`factory.yaml`)
```
ideas:
  url: http://127.0.0.1:3004
  prefix: IDEA
  submission_prefix: IDR
  brand: Acme Ledger · Ideas
  orgs: [acme, globex]          # tokens IDEAS_TOKEN_<ORG>; shares the org list with support
```

## Dependencies and order
[Per-customer boards](per-customer-boards.md) → [support desk](support-desk.md) → ideas. The ideas portal can be built before support, with the
support source switched off until `support/` exists. The portal, internal and tracker sources work
without it.

## Out of scope
- Comments or discussion on published ideas. Customers can't talk to each other; this keeps
  isolation simple.
- Scorecards, effort estimates and roadmaps. Demand count plus the PRD / plan is the roadmap.
- Email notifications. Notices appear on the portal as the submission's status and message.
- Vote weighting by customer size or plan.

## Open questions
1. **Voting identity.** A portal user is an org token plus a typed name, as on the tracker, so one
   person could vote twice under two names. Is that acceptable for a lightweight tool, or should the
   widget-style signed user token from the support spec be used here as well?
2. **Declined ideas.** Should a published idea that is declined stay visible as "not planned" with a
   reason, or be unpublished?
3. **One portal or two.** Should customers reach ideas from the support page (one customer-facing app
   with two tabs), or is it a separate URL?
