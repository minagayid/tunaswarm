# AI Freelance Swarm

A small Python framework for a freelance AI agent swarm: **find -> profile -> win -> deliver -> collect -> allocate**. It persists workflow runs, tracks token spend, and splits profit into owner payout, AI reinvestment, and reserves.

## Repository layout

- `agents/definitions.json`: agent roles, token budgets, default flow
- `orchestration/workflow_engine.py`: SQLite-backed workflow runs and checkpoints
- `tracking/token_tracker.py`: per-agent budgets, usage logging, alerts
- `allocation/profit_allocator.py`: monthly profit reports, allocation rules, allocation history
- `platforms/`: Upwork, Fiverr, and Toptal integration stubs
- `cli/cli.py`: CLI used to run workflow, tokens, and allocation commands

## Requirements

- Python 3.10+ is enough
- No installed packages required beyond the standard library

## Quick start

From `/home/dc-mina/Desktop/ai-freelance-swarm`:

PYTHONPATH=. python3 cli/cli.py workflow start
PYTHONPATH=. python3 cli/cli.py workflow list-runs
PYTHONPATH=. python3 cli/cli.py tokens --init-budget
PYTHONPATH=. python3 cli/cli.py tokens --totals --project run-1
PYTHONPATH=. python3 cli/cli.py allocate --rules --owner 0.6 --reinvestment 0.25 --reserve 0.15
PYTHONPATH=. python3 cli/cli.py allocate --history

## Smoke tests

PYTHONPATH=. python3 tests/smoke_tests.py

Real result as of now: **5/5 smoke tests pass** and the API server (`python3 api/server.py`) is verified end-to-end. Schema files in `orchestration/`, `tracking/`, and `allocation/` initialize the SQLite DBs on first start. Workflow runs can be created, advanced, and queried through the API.

## API

The API listens on `http://127.0.0.1:4123`.

Endpoints:

- `GET  /api/health` - liveness probe
- `GET  /api/runs` - list all workflow runs
- `GET  /api/runs/<id>` - get one workflow run
- `POST /api/runs` - create a workflow run, body `{"run_id": "...", "total_steps": N, "metadata": {...}}`
- `POST /api/runs/<id>/complete` - advance a run by one step, body `{"agent_id": "...", "payload": {...}}`
- `GET  /api/tokens/totals?project=<run_id>` - sum of token spend, optionally filtered by run
- `POST /api/tokens/usage` - log token usage, body `{"run_id", "agent_id", "prompt_tokens", "completion_tokens", "est_cost_usd", "model"}`
- `GET  /api/tokens/budgets` - per-agent token budgets (populated by `cli tokens --init-budget`)
- `GET  /api/allocation/rules` and `PUT /api/allocation/rules` - profit-split rules
- `GET  /api/allocation/history` - applied monthly allocations

End-to-end verification: created run, advanced through 9 agents in `default_flow` (`lead-finder` → `allocator-agent`), and confirmed `current_step=9`, `current_agent=allocator-agent` in the final GET.

## Notes

- All modules use stdlib only - no third-party Python packages required.
- The API server reads schema files from `orchestration/schema.sql`, `tracking/schema.sql`, and `allocation/schema.sql`. These are kept in sync with the `SCHEMA_SQL` constants in each module's Python file.
