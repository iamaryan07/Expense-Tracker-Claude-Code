---
name: project-route-coverage
description: Which Spendly routes have test coverage and which are stubs as of 2026-05-30
metadata:
  type: project
---

## Test coverage status (as of 2026-05-30)

| Route                        | Status in app.py  | Test file                              |
|------------------------------|-------------------|-----------------------------------------|
| GET /                        | Implemented       | none yet                                |
| GET /register + POST         | Implemented       | none yet                                |
| GET /login + POST            | Implemented       | none yet                                |
| GET /logout                  | Implemented       | none yet                                |
| GET /profile (+ date filter) | Implemented       | tests/test_06-date-filter-profile.py    |
| GET+POST /expenses/add       | Implemented       | tests/test_07-add-expense.py            |
| GET+POST /expenses/<id>/edit | Implemented       | tests/test_08-edit-expense.py           |
| GET /expenses/<id>/delete    | Stub (step 9)     | — do not test                           |

## Profile route filter behavior
- `preset` param: `this-month`, `last-month`, `last-3-months`, `all-time` (default), `custom`
- `custom` requires `start` and `end` in YYYY-MM-DD; invalid values silently fall back to all-time
- Active preset marked with `filter-btn--active` CSS class on the anchor
- Human-readable label rendered in `<p class="filter-label">` element
- All three data sections (stats, transactions, categories) use the same date window

**Why:** Avoids writing duplicate tests for already-covered routes and
prevents wasting time on stub routes. [[project-fixture-patterns]]
