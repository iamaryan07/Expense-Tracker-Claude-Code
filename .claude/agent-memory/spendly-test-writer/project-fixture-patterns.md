---
name: project-fixture-patterns
description: Spendly test fixture patterns — how to isolate DB per test, create users, inject sessions
metadata:
  type: project
---

## Fixture pattern for test isolation

`database.db.DB_PATH` is a module-level constant pointing to `spendly.db`.
The app calls `init_db()` + `seed_db()` at module import time inside
`with app.app_context()`, so tests must patch `DB_PATH` before the test client
makes any DB calls.

**Correct approach:**
1. Create a `tempfile.mkstemp(suffix=".db")` per test.
2. Use `patch.object(db_module, "DB_PATH", tmp_path)` as a context manager
   wrapping both `app.test_client()` and all DB helper calls.
3. Call `init_db()` inside `app.app_context()` to create the schema.
4. Insert controlled rows directly via `get_db()` with parameterized queries.
5. Delete the temp file in fixture teardown.

**Session injection (no form login needed):**
```python
with client.session_transaction() as sess:
    sess["user_id"] = user_id
```

**Why:** The app module-level `seed_db()` populates `spendly.db` with demo
data at startup. Without patching `DB_PATH`, every test shares that polluted
state and date-range assertions become unpredictable.

**How to apply:** Always use this pattern for any test that touches `/profile`,
`/login`, `/register`, or any expense route. Never rely on the seed data for
date-sensitive assertions. [[project-db-schema]]
