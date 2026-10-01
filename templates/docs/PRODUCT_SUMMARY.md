# {{project_name}} — Product Summary

**Date:** {{date}} · **Owner:** {{owner}} · **Status:** {{status}}
**Source:** `/product-interview` with {{owner}}. The input to `/setup-project`; amended by
re-running the interview, never edited silently. `[assumed]` marks anything the owner has
not confirmed.

> **{{one_liner}}**
> *For {{primary_persona}}, who {{core_job}}, {{project_name}} {{value_in_one_line}} —
> unlike {{main_alternative}}.*

---

## 1. Personas (customer segments)

| Id | Who | Context — when and where they meet the product | Primary? |
|---|---|---|---|
{{persona_rows}}

---

## 2. Value proposition canvas

One canvas per primary persona (Osterwalder). The **customer profile** is what is true of
the persona with or without this product; the **value map** is what the product does about
it. Ranks run from 1 (most important).

### 2.{{n}} — {{persona}}

**Jobs to be done**

| # | Kind | Job — *When I …, I want to …, so I can …* | Rank |
|---|---|---|---|
{{job_rows}}

**Pains** — what annoys them, blocks them or puts them at risk before, during or after the job

| # | Pain | Concrete instance (the last time it happened) | Severity (1–5) | Rank |
|---|---|---|---|---|
{{pain_rows}}

**Gains** — outcomes and benefits they want

| # | Gain | Level (required · expected · desired · unexpected) | Rank |
|---|---|---|---|
{{gain_rows}}

**Value map**

| Products & services | Pain relievers | Gain creators |
|---|---|---|
{{value_map_rows}}

**Fit** — every top-ranked pain and gain is met, or knowingly left open

| Pain / gain | Met by | Component tool | Strength (strong · partial · open) |
|---|---|---|---|
{{fit_rows}}

---

## 3. Component tools (modules)

The parts of the product. Each becomes a module id in `factory.yaml` and a `§3.N` section in
the PRD.

| Id | Tool | What it does | Serves (job / pain / gain) | MoSCoW |
|---|---|---|---|---|
{{tool_rows}}

---

## 4. Inspiration & alternatives

**What the persona does today instead**

| Alternative | What it gets right | Where it fails them |
|---|---|---|
{{alternative_rows}}

**Inspiration** — products or ideas to borrow from

| Source | What to borrow | What not to copy |
|---|---|---|
{{inspiration_rows}}

---

## 5. Success metrics (3 months)

| Metric | Today | Target | How it is measured |
|---|---|---|---|
{{metric_rows}}

---

## 6. Stack & deploy

| Layer | Choice |
|---|---|
| Frontend | {{frontend}} |
| Backend | {{backend}} |
| End-to-end tests | {{e2e}} |
| Design system | {{design_system}} |
| Deploy target | {{deploy_target}} |
| Environments | {{environments}} |
| Seed / demo data | {{seed}} |

---

## 7. Open questions & assumptions

| # | Question or assumption | Why it matters | Owner |
|---|---|---|---|
{{open_rows}}
