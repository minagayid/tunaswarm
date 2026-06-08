"""Freelance Swarm Orchestration Engine"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    current_agent TEXT,
    current_step INTEGER,
    total_steps INTEGER,
    created_at TEXT,
    updated_at TEXT,
    finished_at TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS workflow_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT
);

CREATE TABLE IF NOT EXISTS workflow_checkpoints (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    state_dir TEXT NOT NULL,
    metadata TEXT
);
"""


@dataclass
class WorkflowEvent:
    ts: str
    agent_id: str
    event_type: str
    payload: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowRun:
    id: str
    status: str
    current_agent: Optional[str] = None
    current_step: Optional[int] = None
    total_steps: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    finished_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class WorkflowEngine:
    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "workflow.db"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    def start_run(self, run_id: str, total_steps: int, metadata: Optional[Dict[str, Any]] = None) -> WorkflowRun:
        now = datetime.now(timezone.utc).isoformat()
        run = WorkflowRun(
            id=run_id,
            status="running",
            current_step=0,
            total_steps=total_steps,
            created_at=now,
            updated_at=now,
            metadata=metadata,
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO workflow_runs (id, status, current_agent, current_step, total_steps, created_at, updated_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (run.id, run.status, run.current_agent, run.current_step, run.total_steps, run.created_at, run.updated_at, json.dumps(run.metadata or {})),
            )
            conn.commit()
        self._record_event(run_id, "system", "run_started", {"total_steps": total_steps})
        return run

    def record_agent_complete(self, run_id: str, agent_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._record_event(run_id, agent_id, "agent_completed", payload)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT current_step, total_steps FROM workflow_runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Run not found: {run_id}")
            current_step, total_steps = row
            current_step = (current_step or 0) + 1
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE workflow_runs SET current_step = ?, current_agent = ?, updated_at = ? WHERE id = ?",
                (current_step, agent_id, now, run_id),
            )
            conn.commit()
        return {"next_step": current_step, "total_steps": total_steps}

    def fail_run(self, run_id: str, agent_id: str, error: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE workflow_runs SET status = 'failed', current_agent = ?, updated_at = ?, finished_at = ? WHERE id = ?",
                (agent_id, now, now, run_id),
            )
            conn.commit()
        self._record_event(run_id, agent_id, "run_failed", {"error": error})

    def complete_run(self, run_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE workflow_runs SET status = 'completed', current_step = total_steps, updated_at = ?, finished_at = ? WHERE id = ?",
                (now, now, run_id),
            )
            conn.commit()
        self._record_event(run_id, "system", "run_completed", {})

    def get_run(self, run_id: str) -> Optional[WorkflowRun]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id, status, current_agent, current_step, total_steps, created_at, updated_at, finished_at, metadata FROM workflow_runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
        if not row:
            return None
        run = WorkflowRun(
            id=row[0],
            status=row[1],
            current_agent=row[2],
            current_step=row[3],
            total_steps=row[4],
            created_at=row[5],
            updated_at=row[6],
            finished_at=row[7],
            metadata=json.loads(row[8]) if row[8] else {},
        )
        return run

    def _record_event(self, run_id: str, agent_id: Optional[str], event_type: str, payload: Optional[Dict[str, Any]]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO workflow_events (run_id, ts, agent_id, event_type, payload) VALUES (?, ?, ?, ?, ?)",
                (run_id, datetime.now(timezone.utc).isoformat(), agent_id, event_type, json.dumps(payload or {})),
            )
            conn.commit()

    def create_checkpoint(self, run_id: str, agent_id: str, state_dir: str) -> str:
        checkpoint_id = f"cp-{run_id}-{agent_id}-{int(datetime.now(timezone.utc).timestamp())}"
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO workflow_checkpoints (id, run_id, agent_id, created_at, state_dir, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (checkpoint_id, run_id, agent_id, now, state_dir, "{}"),
            )
            conn.commit()
        return checkpoint_id
