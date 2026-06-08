CREATE TABLE IF NOT EXISTS agent_budgets (
    agent_id TEXT PRIMARY KEY,
    budget_per_run INTEGER NOT NULL,
    max_consecutive_runs INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS token_usages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    run_id TEXT,
    agent_id TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    est_cost_usd REAL NOT NULL,
    model TEXT
);

CREATE TABLE IF NOT EXISTS spending_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    run_id TEXT,
    alert_type TEXT NOT NULL,
    detail TEXT
);
