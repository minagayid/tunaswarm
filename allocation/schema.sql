CREATE TABLE IF NOT EXISTS monthly_profit_reports (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    revenue_usd REAL NOT NULL,
    ai_cost_usd REAL NOT NULL,
    platform_fees_usd REAL NOT NULL,
    net_profit_usd REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monthly_allocations (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    owner_payout_usd REAL NOT NULL,
    ai_reinvestment_usd REAL NOT NULL,
    emergency_reserve_usd REAL NOT NULL,
    rules_snapshot TEXT NOT NULL,
    created_at TEXT NOT NULL
);
