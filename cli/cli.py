"""Freelance Swarm CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from orchestration.workflow_engine import WorkflowEngine
from tracking.token_tracker import TokenTracker, AgentBudget
from allocation.profit_allocator import ProfitAllocator, AllocationRules


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Freelance Swarm CLI")
    sub = parser.add_subparsers(dest="command")

    workflow = sub.add_parser("workflow", help="Workflow commands")
    workflow_sub = workflow.add_subparsers(dest="workflow_command")
    workflow_sub.add_parser("list-runs", help="List workflow runs")
    workflow_sub.add_parser("start", help="Start a new workflow run")
    w_get = workflow_sub.add_parser("get", help="Get a run")
    w_get.add_argument("run_id")
    w_resume = workflow_sub.add_parser("resume", help="Resume a run")
    w_resume.add_argument("run_id")
    w_resume.add_argument("agent_id")

    tokens = sub.add_parser("tokens", help="Token tracking commands")
    tokens.add_argument("--init-budget", action="store_true", help="Initialize budgets from agents/definitions.json")
    tokens.add_argument("--totals", action="store_true", help="Show totals")
    tokens.add_argument("--project", help="Filter totals by project/run ID")

    alloc = sub.add_parser("allocate", help="Profit allocation commands")
    alloc.add_argument("--report", action="store_true", help="Create a monthly report")
    alloc.add_argument("--apply", action="store_true", help="Apply allocation rules to latest report")
    alloc.add_argument("--history", action="store_true", help="Show allocation history")
    alloc.add_argument("--rules", action="store_true", help="Set allocation rules")
    alloc.add_argument("--owner", type=float, help="Owner payout percentage")
    alloc.add_argument("--reinvestment", type=float, help="AI reinvestment percentage")
    alloc.add_argument("--reserve", type=float, help="Emergency reserve percentage")

    return parser


def init_budgets(data_dir: Path) -> None:
    tracker = TokenTracker(data_dir=data_dir.as_posix())
    definitions_path = data_dir.parent / "agents" / "definitions.json"
    with open(definitions_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for agent in data["agents"]:
        budget = AgentBudget(
            agent_id=agent["id"],
            budget_per_run=int(agent.get("token_budget_per_run", 0)),
            max_consecutive_runs=int(agent.get("max_consecutive_runs", 0)),
            updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        )
        tracker.upsert_budget(budget)
        print(f"Budget set: {agent['id']} -> {budget.budget_per_run} tokens/run")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    # Resolve data dir relative to repo root for convenience
    data_dir = Path(__file__).resolve().parents[1] / "data"

    if args.command == "tokens":
        tracker = TokenTracker(data_dir=data_dir.as_posix())
        if args.init_budget:
            init_budgets(data_dir)
            return 0
        if args.totals:
            run_id = args.project
            total = tracker.total_cost(run_id=run_id)
            print(json.dumps({"run_id": run_id, "total_cost_usd": total}, indent=2))
            return 0

    if args.command == "workflow":
        engine = WorkflowEngine(data_dir=data_dir.as_posix())
        if args.workflow_command == "list-runs":
            with __import__("sqlite3").connect((data_dir / "workflow.db").as_posix()) as conn:
                rows = conn.execute("SELECT id, status, current_agent, current_step, total_steps, updated_at FROM workflow_runs ORDER BY created_at DESC").fetchall()
            for row in rows:
                print(json.dumps({"id": row[0], "status": row[1], "current_agent": row[2], "current_step": row[3], "total_steps": row[4], "updated_at": row[5]}, indent=2))
            return 0
        if args.workflow_command == "start":
            run_id = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("run-%Y%m%d-%H%M%S")
            run = engine.start_run(run_id=run_id, total_steps=5, metadata={"runner": "cli"})
            print(json.dumps({"run_id": run.id, "status": run.status, "current_step": run.current_step, "total_steps": run.total_steps}, indent=2))
            return 0
        if args.workflow_command == "get":
            run = engine.get_run(args.run_id)
            if not run:
                print(json.dumps({"error": f"Run not found: {args.run_id}"}), file=sys.stderr)
                return 1
            print(json.dumps({"id": run.id, "status": run.status, "current_agent": run.current_agent, "current_step": run.current_step, "total_steps": run.total_steps, "created_at": run.created_at, "updated_at": run.updated_at}, indent=2))
            return 0

    if args.command == "allocate":
        allocator = ProfitAllocator(data_dir=data_dir.as_posix())
        if args.history:
            print(json.dumps(allocator.latest_allocations(), indent=2))
            return 0
        if args.rules:
            rules = AllocationRules(
                owner_payout_pct=args.owner or 0.60,
                ai_reinvestment_pct=args.reinvestment or 0.25,
                emergency_reserve_pct=args.reserve or 0.15,
            )
            # Persist rules in a local rules file for reuse.
            rules_path = data_dir / "allocation_rules.json"
            rules_path.write_text(json.dumps(rules.to_dict(), indent=2), encoding="utf-8")
            print(json.dumps({"saved_rules": rules.to_dict(), "path": str(rules_path)}, indent=2))
            return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
