"""Token-cost tracker for the freelance swarm."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA_SQL = """
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
"""


@dataclass
class TokenUsage:
    ts: str
    run_id: Optional[str]
    agent_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    est_cost_usd: float
    model: Optional[str] = None


@dataclass
class AgentBudget:
    agent_id: str
    budget_per_run: int
    max_consecutive_runs: int
    updated_at: str


class TokenTracker:
    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "tracking.db"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    def upsert_budget(self, budget: AgentBudget) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO agent_budgets (agent_id, budget_per_run, max_consecutive_runs, updated_at) VALUES (?, ?, ?, ?)",
                (budget.agent_id, budget.budget_per_run, budget.max_consecutive_runs, budget.updated_at),
            )
            conn.commit()

    def record_usage(self, usage: TokenUsage) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO token_usages (ts, run_id, agent_id, prompt_tokens, completion_tokens, total_tokens, est_cost_usd, model) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (usage.ts, usage.run_id, usage.agent_id, usage.prompt_tokens, usage.completion_tokens, usage.total_tokens, usage.est_cost_usd, usage.model),
            )
            conn.commit()
        self._check_alerts(usage)

    def total_cost(self, run_id: Optional[str] = None) -> float:
        query = "SELECT SUM(est_cost_usd) FROM token_usages"
        args: tuple[Any, ...] = ()
        if run_id:
            query += " WHERE run_id = ?"
            args = (run_id,)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, args)
            row = cursor.fetchone()
        return float(row[0] or 0.0)

    def total_by_project(self, project_id: str) -> float:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT SUM(est_cost_usd) FROM token_usages WHERE run_id = ?", (project_id,))
            row = cursor.fetchone()
        return float(row[0] or 0.0)

    def _check_alerts(self, usage: TokenUsage) -> None:
        # Budget-based alert: if total tokens exceed budget_per_run for this agent, record alert.
        budget = self.get_budget(usage.agent_id)
        if not budget:
            return
        now = datetime.now(timezone.utc).isoformat()
        if usage.total_tokens > budget.budget_per_run:
            self._insert_alert(now, usage.agent_id, usage.run_id, "budget_exceeded", f"used {usage.total_tokens} > budget {budget.budget_per_run}")

    def _insert_alert(self, ts: str, agent_id: str, run_id: Optional[str], alert_type: str, detail: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO spending_alerts (ts, agent_id, run_id, alert_type, detail) VALUES (?, ?, ?, ?, ?)",
                (ts, agent_id, run_id, alert_type, detail),
            )
            conn.commit()

    def get_budget(self, agent_id: str) -> Optional[AgentBudget]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT agent_id, budget_per_run, max_consecutive_runs, updated_at FROM agent_budgets WHERE agent_id = ?", (agent_id,))
            row = cursor.fetchone()
        if not row:
            return None
        return AgentBudget(agent_id=row[0], budget_per_run=row[1], max_consecutive_runs=row[2], updated_at=row[3])

    def list_budgets(self) -> List[AgentBudget]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT agent_id, budget_per_run, max_consecutive_runs, updated_at FROM agent_budgets")
            rows = cursor.fetchall()
        return [AgentBudget(agent_id=r[0], budget_per_run=r[1], max_consecutive_runs=r[2], updated_at=r[3]) for r in rows]
