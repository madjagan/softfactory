# {{project_name}} — Product Feature List & Traceability

**Version:** 0.1 · **Date:** {{date}} · **Owner:** {{owner}}
**Purpose:** the authoritative capability inventory, for deriving user documentation and
customer communication. The user guides in `user-guide/` are generated from this file.

---

## 0. How to read this document

**Inputs.** `PRODUCT_REQUIREMENTS.md` (the dated §3 sections), `IMPLEMENTATION_PLAN.md`
(delivery status per section), the codebase where documents disagree.

**Scope decisions.**
1. **Shipped capabilities only** carry a `●`. Anything planned appears here as `◐` or in
   §8 (gap register), never as live.
2. **Capability-level granularity.** One or two features per PRD section.
3. **Maturity is stated per feature** and known gaps are listed openly in §8.

| Column | Meaning |
|---|---|
| **ID** | Stable feature id (`AREA-NN`). Use these in user docs and release notes. Never renumber. |
| **Req IDs** | PRD section(s) the feature satisfies. |
| **Pri** | MoSCoW for the shipped scope: `M` must · `S` should · `C` could. `W` is §7. |
| **Mat** | **●** Live: an engine computes it, writes persist through their own route, the screen reads that back, a test pins it. **◐** In development: screens / data only, or simulated. **◐!** a specific caveat named in the row. |
| **Personas** | See §2. |
| **Deps** | Other feature ids this one requires. |

**A note on honesty.** Where a shipped screen displays something the engine does not
enforce, the row says so. Customer-facing material derived from this document must carry
those caveats forward.

---

## 1. Product one-liner

{{summary_one_line}}

## 2. Personas

| Id | Persona | What that reader does |
|---|---|---|
{{persona_rows}}

---

## 3. Feature catalogue

### 3.1 {{area_1}}

| ID | Feature | Req IDs | Pri | Mat | Personas | Acceptance (short) | Deps |
|---|---|---|---|---|---|---|---|
| **{{AREA}}-01** | … | §3.1 | M | ◐ | P1 | … | — |

---

## 4. Traceability: PRD section → feature id

| PRD § | Feature ids |
|---|---|
| 3.1 | {{AREA}}-01 |

---

## 5. Persona × feature matrix

(Generated from §3 when the catalogue is stable.)

---

## 6. Feature scope per persona guide

| Guide file | Persona | Feature ids |
|---|---|---|
{{guide_scope_rows}}

---

## 7. Explicitly out of scope (the "Won't" of this version)

1. …

---

## 8. Gap register

Known gaps between what a screen shows and what the engine does, and Must / Should items
not yet built. Ids `A-n` (must-fix before customer use), `B-n` (must, functional),
`C-n` (should), `D-n` (could).

| Id | Gap | Against | Pri | Note |
|---|---|---|---|---|
| — | — | — | — | Empty on day one. |

---

## 9. Recommended additions

| Id | Recommendation | Closes |
|---|---|---|
| — | — | — |

---

## Revision history

- **0.1 ({{date}})** — created by `/setup-project` from the product summary.
