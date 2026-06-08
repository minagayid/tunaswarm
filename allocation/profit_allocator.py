"""Profit allocation engine.

Allocates net profit into AI reinvestment, owner payout, and reserves.
Rules are persisted in SQLite and can be changed without code edits.
"""

from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA_SQL = """
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
"""


@dataclass(frozen=True)
class AllocationRules:
    owner_payout_pct: float = 0.60
    ai_reinvestment_pct: float = 0.25
    emergency_reserve_pct: float = 0.15

    def to_dict(self) -> Dict[str, float]:
        return {
            "owner_payout_pct": self.owner_payout_pct,
            "ai_reinvestment_pct": self.ai_reinvestment_pct,
            "emergency_reserve_pct": self.emergency_reserve_pct,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "AllocationRules":
        return cls(
            owner_payout_pct=float(data.get("owner_payout_pct", 0.60)),
            ai_reinvestment_pct=float(data.get("ai_reinvestment_pct", 0.25)),
            emergency_reserve_pct=float(data.get("emergency_reserve_pct", 0.15)),
        )


@dataclass
class MonthlyReport:
    id: str
    year: int
    month: int
    revenue_usd: float
    ai_cost_usd: float
    platform_fees_usd: float
    net_profit_usd: float
    created_at: str


@dataclass
class MonthlyAllocation:
    id: str
    report_id: str
    year: int
    month: int
    owner_payout_usd: float
    ai_reinvestment_usd: float
    emergency_reserve_usd: float
    rules_snapshot: Dict[str, Any]
    created_at: str


class ProfitAllocator:
    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "allocation.db"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    def create_monthly_report(self, year: int, month: int, revenue_usd: float, ai_cost_usd: float, platform_fees_usd: float) -> MonthlyReport:
        now = datetime.now(timezone.utc).isoformat()
        net_profit = float(revenue_usd or 0.0) - float(ai_cost_usd or 0.0) - float(platform_fees_usd or 0.0)
        report_id = f"mrr-{year}-{month:02d}"
        report = MonthlyReport(id=report_id, year=year, month=month, revenue_usd=revenue_usd, ai_cost_usd=ai_cost_usd, platform_fees_usd=platform_fees_usd, net_profit_usd=net_profit, created_at=now)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO monthly_profit_reports (id, year, month, revenue_usd, ai_cost_usd, platform_fees_usd, net_profit_usd, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (report.id, report.year, report.month, report.revenue_usd, report.ai_cost_usd, report.platform_fees_usd, report.net_profit_usd, report.created_at),
            )
            conn.commit()
        return report

    def allocate_profit(self, report_id: str, rules: Optional[AllocationRules] = None) -> MonthlyAllocation:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT year, month, net_profit_usd FROM monthly_profit_reports WHERE id = ?", (report_id,))
            row = cursor.fetchone()
        if not row:
            raise ValueError(f"Report not found: {report_id}")
        year, month, net_profit_usd = row
        rules = rules or AllocationRules()
        owner_payout = round(net_profit_usd * rules.owner_payout_pct, 2)
        ai_reinvestment = round(net_profit_usd * rules.ai_reinvestment_pct, 2)
        emergency_reserve = round(net_profit_usd * rules.emergency_reserve_pct, 2)
        allocation_id = report_id.replace("mrr-", "alloc-")
        now = datetime.now(timezone.utc).isoformat()
        allocation = MonthlyAllocation(id=allocation_id, report_id=report_id, year=year, month=month, owner_payout_usd=owner_payout, ai_reinvestment_usd=ai_reinvestment, emergency_reserve_usd=emergency_reserve, rules_snapshot=rules.to_dict(), created_at=now)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO monthly_allocations (id, report_id, year, month, owner_payout_usd, ai_reinvestment_usd, emergency_reserve_usd, rules_snapshot, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (allocation.id, allocation.report_id, allocation.year, allocation.month, allocation.owner_payout_usd, allocation.ai_reinvestment_usd, allocation.emergency_reserve_usd, json.dumps(allocation.rules_snapshot), allocation.created_at),
            )
            conn.commit()
        return allocation

    def latest_allocations(self, limit: int = 12) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, year, month, owner_payout_usd, ai_reinvestment_usd, emergency_reserve_usd, rules_snapshot, created_at FROM monthly_allocations ORDER BY year DESC, month DESC LIMIT ?",
                (int(limit),),
            )
            rows = cursor.fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            out.append({"id": row[0], "year": row[1], "month": row[2], "owner_payout_usd": row[3], "ai_reinvestment_usd": row[4], "emergency_reserve_usd": row[5], "rules": json.loads(row[6]), "created_at": row[7]})
        return out
