# Seeding — which seeder to run and why

Picking the wrong seeder destroys live data. Read this before touching seed data.

## The seeders

| Command | What it does | Safe on |
|---|---|---|
| `{{reseed}}` | {{reseed_description}} | {{reseed_safe_on}} |
| — | — | — |

Rules:
- **Always back up first** ({{backup_command}}); backups live in {{backup_location}}.
- **Replay through the services**, not snapshot inserts: balances, chains, history and
  the audit trail must be written by the code that owns them, or they contradict each other.
- **Test database vs dev database.** The e2e harness fresh-seeds its own database each run.
  The dev database keeps hand-inspected scenarios and is never truncated by a test.
- **Two runners, one database → collisions.** If ids are count-based, run the backend suite
  and the e2e suite one at a time after a reseed.
- **The narrative date** ({{narrative_date}}) is the fixed date the seeded story is
  written around. It is separate from the clock seam. Changing it changes what every
  seeded countdown renders — a product decision, not a refactor.

## Writing or extending a scenario

1. State the persona, the period and the outcome the scenario must make visible.
2. Drive it through the same code path a user would (API calls inside a frozen clock).
3. Assert the outcome in a test that reruns the scenario from a clean seed.
4. Record the scenario here with its spec file and the records it creates.
