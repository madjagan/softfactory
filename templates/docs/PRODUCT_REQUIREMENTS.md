# {{project_name}} — Product Requirements Document

**Version:** 0.1 · **Date:** {{date}} · **Owner:** {{owner}}
**Sources:** the product summary of {{date}}; amended continuously — every change to a
requirement is a dated amendment under its section, never a silent rewrite.

---

## 1. Purpose & vision

{{summary}}

**Product principles**

1. {{principle_1}}
2. {{principle_2}}
3. {{principle_3}}

---

## 2. Users & roles

| Persona | Reach |
|---|---|
{{persona_rows}}

---

## 3. Requirements

> One section per capability. Each carries a **date**, a **user story**, **numbered
> observable acceptance criteria**, **scope / non-goals**, and its impact on personas,
> access and data. A section is **Complete** only when the test file named for it in
> `IMPLEMENTATION_PLAN.md` passes in the verify gate. Changes are **dated amendments**:
> `**Amendment (YYYY-MM-DD):** was …; now …; because ….`

### §3.1 — {{module_1_title}}

- **Date:** {{date}} · **Status:** Planned
- **User story:** As a {{persona}}, I want {{capability}} so that {{value}}.
- **Acceptance criteria**
  1. {{observable statement a test can check}}
  2. …
- **Scope / non-goals:** …
- **Personas / access / data impact:** …

### §3.2 — {{module_2_title}}

(same shape)

---

## 4. Cross-cutting requirements

### §4.1 — Access model
Who may open which module, and what a role may do inside it. Visibility gates (role,
feature flag, deployment config) are orthogonal; effective visibility is their intersection.

### §4.2 — Auditability
Every write that changes money, status or access is attributable to a user and a time.

### §4.3 — Time
The application reads time through one seam per side; tests freeze it.

---

## 5. Out of scope (the explicit "Won't" of this version)

1. …

---

## 6. Glossary

| Term | Meaning |
|---|---|
| … | … |
