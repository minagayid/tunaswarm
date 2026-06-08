"""Sandboxed agent runner for the freelance swarm workflow.

Consumes a WorkflowEngine run, executes one agent step, records the
result, and advances the run.  Each agent returns a local artifact
dict that becomes the ``payload`` for the workflow event.

Pure stdlib.  No network dependencies.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from orchestration.workflow_engine import WorkflowEngine
from tracking.token_tracker import TokenTracker, TokenUsage


class AgentContext:
    """Lightweight per-run state bag passed between agents."""

    def __init__(self) -> None:
        self.artifacts: Dict[str, Any] = {}

    def set(self, name: str, value: Any) -> None:
        self.artifacts[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        return self.artifacts.get(name, default)


class AgentError(Exception):
    """Raised when an agent step cannot be executed cleanly."""


def _cost(agent_id: str, prompt: int = 0, completion: int = 0, usd: float = 0.0, model: str = "stub") -> Dict[str, Any]:
    return {
        "agent_id": agent_id,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "est_cost_usd": round(usd, 4),
        "model": model,
    }


# ---------------------------------------------------------------------------
# Agent implementations
# Each returns a dict that is stored as the event payload.
# ---------------------------------------------------------------------------

def run_lead_finder(ctx: AgentContext, run_id: str, tracker: TokenTracker) -> Dict[str, Any]:
    from platforms.upwork_stub import UpworkClient
    from platforms.fiverr_stub import FiverrClient
    from platforms.toptal_stub import ToptalClient

    upwork = UpworkClient()
    fiverr = FiverrClient()
    toptal = ToptalClient()

    leads: list = []
    for client in (upwork, fiverr, toptal):
        jobs = client.fetch_jobs(limit=10)
        for j in jobs:
            score = round(min(j.budget_usd or 0, 5000) / 5000, 2)
            leads.append(
                {
                    "id": j.id,
                    "platform": j.platform,
                    "title": j.title,
                    "budget_usd": j.budget_usd,
                    "score": score,
                }
            )

    tracker.record_usage(
        TokenUsage(
            ts=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            agent_id="lead-finder",
            prompt_tokens=800,
            completion_tokens=1200,
            total_tokens=2000,
            est_cost_usd=0.04,
            model="stub",
        )
    )
    return {"leads": leads[:10], "count": len(leads)}


def run_profile_optimizer(ctx: AgentContext, run_id: str, tracker: TokenTracker) -> Dict[str, Any]:
    leads = ctx.get("leads", {}).get("leads", []) if isinstance(ctx.get("leads"), dict) else []

    proposals: list = []
    for lead in leads[:3]:
        proposals.append(
            {
                "lead_id": lead["id"],
                "platform": lead["platform"],
                "proposal": f"Proposal for {lead['title']}",
                "tone": "professional",
            }
        )

    tracker.record_usage(
        TokenUsage(
            ts=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            agent_id="profile-optimizer",
            prompt_tokens=1600,
            completion_tokens=1400,
            total_tokens=3000,
            est_cost_usd=0.06,
            model="stub",
        )
    )
    return {"proposals": proposals, "variant_count": len(proposals)}


def run_project_manager(ctx: AgentContext, run_id: str, tracker: TokenTracker) -> Dict[str, Any]:
    proposals = ctx.get("proposals", {}).get("proposals", []) if isinstance(ctx.get("proposals"), dict) else []

    milestones: list = []
    for i, p in enumerate(proposals[:2] or [{"lead_id": "demo-1", "platform": "upwork"}], start=1):
        milestones.append(
            {
                "milestone": i,
                "lead_id": p.get("lead_id"),
                "tasks": ["plan", "implement", "review"],
                "estimated_hours": 8 * i,
            }
        )

    tracker.record_usage(
        TokenUsage(
            ts=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            agent_id="project-manager",
            prompt_tokens=1200,
            completion_tokens=1300,
            total_tokens=2500,
            est_cost_usd=0.05,
            model="stub",
        )
    )
    return {"milestones": milestones, "project_count": len(milestones)}


def run_code_agent(ctx: AgentContext, run_id: str, tracker: TokenTracker) -> Dict[str, Any]:
    milestones = ctx.get("milestones", {}).get("milestones", [])

    deliverables: list = []
    for ms in milestones:
        deliverables.append(
            {
                "milestone": ms["milestone"],
                "files": [f"src/m{ms['milestone']}/main.py", f"tests/test_m{ms['milestone']}.py"],
                "tests_passing": True,
                "lint_ok": True,
            }
        )

    tracker.record_usage(
        TokenUsage(
            ts=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            agent_id="code-agent",
            prompt_tokens=3500,
            completion_tokens=4500,
            total_tokens=8000,
            est_cost_usd=0.18,
            model="stub",
        )
    )
    return {"deliverables": deliverables, "ready_for_qa": True}


def run_qa_agent(ctx: AgentContext, run_id: str, tracker: TokenTracker) -> Dict[str, Any]:
    deliverables = ctx.get("deliverables", {}).get("deliverables", [])

    approved = True
    for d in deliverables:
        if not d.get("tests_passing") or not d.get("lint_ok"):
            approved = False
            break

    tracker.record_usage(
        TokenUsage(
            ts=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            agent_id="qa-agent",
            prompt_tokens=1500,
            completion_tokens=1500,
            total_tokens=3000,
            est_cost_usd=0.07,
            model="stub",
        )
    )
    return {"approved": approved, "deliverables_reviewed": len(deliverables)}


def run_billing_agent(ctx: AgentContext, run_id: str, tracker: TokenTracker) -> Dict[str, Any]:
    deliverables = ctx.get("deliverables", {}).get("deliverables", []) or []
    approved = ctx.get("qa", {}).get("approved", False)

    invoices: list = []
    if approved:
        for i, d in enumerate(deliverables, start=1):
            invoices.append(
                {
                    "invoice_id": f"inv-{run_id}-{i}",
                    "milestone": d["milestone"],
                    "amount_usd": 400.0 * d["milestone"],
                    "status": "generated",
                }
            )

    tracker.record_usage(
        TokenUsage(
            ts=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            agent_id="billing-agent",
            prompt_tokens=700,
            completion_tokens=800,
            total_tokens=1500,
            est_cost_usd=0.03,
            model="stub",
        )
    )
    return {"invoices": invoices, "count": len(invoices)}


def run_collector_agent(ctx: AgentContext, run_id: str, tracker: TokenTracker) -> Dict[str, Any]:
    invoices = ctx.get("invoices", {}).get("invoices", [])

    payments: list = []
    for inv in invoices:
        payments.append(
            {
                "invoice_id": inv["invoice_id"],
                "status": "paid",
                "paid_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    tracker.record_usage(
        TokenUsage(
            ts=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            agent_id="collector-agent",
            prompt_tokens=600,
            completion_tokens=600,
            total_tokens=1200,
            est_cost_usd=0.02,
            model="stub",
        )
    )
    return {"payments": payments, "cashflow_recorded": True}


def run_economics_agent(ctx: AgentContext, run_id: str, tracker: TokenTracker) -> Dict[str, Any]:
    total_cost = tracker.total_cost(run_id=run_id)
    invoices = ctx.get("invoices", {}).get("invoices", []) or []
    revenue = sum(inv.get("amount_usd", 0) for inv in invoices)
    net = round(revenue - total_cost, 2)
    margin = round(net / revenue, 2) if revenue else 0.0

    tracker.record_usage(
        TokenUsage(
            ts=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            agent_id="economics-agent",
            prompt_tokens=1000,
            completion_tokens=1000,
            total_tokens=2000,
            est_cost_usd=0.05,
            model="stub",
        )
    )
    return {"revenue_usd": revenue, "ai_cost_usd": round(total_cost, 4), "net_profit_usd": net, "margin_pct": margin}


def run_allocator_agent(ctx: AgentContext, run_id: str, tracker: TokenTracker) -> Dict[str, Any]:
    econ = ctx.get("economics", {}) or {}
    net = econ.get("net_profit_usd", 0.0)

    rules_path = Path(__file__).resolve().parents[1] / "data" / "allocation_rules.json"
    try:
        rules = json.loads(rules_path.read_text()) if rules_path.exists() else {}
    except Exception:
        rules = {}

    owner = round(net * rules.get("owner_payout_pct", 0.60), 2)
    reinvest = round(net * rules.get("ai_reinvestment_pct", 0.25), 2)
    reserve = round(net * rules.get("emergency_reserve_pct", 0.15), 2)

    tracker.record_usage(
        TokenUsage(
            ts=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            agent_id="allocator-agent",
            prompt_tokens=800,
            completion_tokens=700,
            total_tokens=1500,
            est_cost_usd=0.03,
            model="stub",
        )
    )
    return {
        "net_profit_usd": net,
        "owner_payout_usd": owner,
        "ai_reinvestment_usd": reinvest,
        "emergency_reserve_usd": reserve,
        "rules_used": rules,
    }


# ---------------------------------------------------------------------------
# New agents: scraping, senior-engineer, cybersecurity
# ---------------------------------------------------------------------------

def _record_scraping_usage(run_id: str, tracker: TokenTracker, prompt: int, completion: int, usd: float) -> None:
    tracker.record_usage(
        TokenUsage(
            ts=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            agent_id="scraping-agent",
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
            est_cost_usd=round(usd, 4),
            model="stub",
        )
    )


def run_scraping_agent(ctx: AgentContext, run_id: str, tracker: TokenTracker) -> Dict[str, Any]:
    """Scrape X/Twitter and Reddit for real-world problems and pain points."""
    # In a real implementation this would call external APIs (Twitter API v2,
    # PRAW/Reddit API, or a Brave/Google search).  Here we produce a
    # deterministic sample output so the workflow can still run end-to-end.
    sample_problems = [
        {"source": "reddit", "subreddit": "r/programming", "title": "CI/CD pipelines are too complex for small teams", "upvotes": 342, "category": "devops"},
        {"source": "reddit", "subreddit": "r/saas", "title": "Customer onboarding emails go to spam too often", "upvotes": 218, "category": "email"},
        {"source": "x", "query": "#buildinpublic", "title": "Stripe webhooks are a pain to test locally", "upvotes": 156, "category": "payments"},
        {"source": "reddit", "subreddit": "r/webdev", "title": "Form validation libraries are over-engineered", "upvotes": 189, "category": "frontend"},
        {"source": "x", "query": "#indiehacker", "title": "Analytics dashboards cost more than the product itself", "upvotes": 97, "category": "analytics"},
    ]
    validated = [
        {**p, "validated": True, "confidence": round(p["upvotes"] / 500, 2)}
        for p in sample_problems
        if p["upvotes"] > 100
    ]

    _record_scraping_usage(run_id, tracker, prompt=2200, completion=2800, usd=0.11)
    return {
        "problem_signals": sample_problems,
        "validated_problems": validated,
        "trending_topics": ["devops", "email-deliverability", "payments", "frontend", "analytics"],
        "signal_count": len(sample_problems),
        "validated_count": len(validated),
    }


def run_senior_engineer_agent(ctx: AgentContext, run_id: str, tracker: TokenTracker) -> Dict[str, Any]:
    """Build a production-ready website/webapp solving the top validated problem."""
    problems = ctx.get("scraping", {}).get("validated_problems", []) if isinstance(ctx.get("scraping"), dict) else []
    top = max(problems, key=lambda p: p.get("confidence", 0)) if problems else {}

    # In the real version this would scaffold code into a project dir,
    # write a Dockerfile + CI config, and deploy.  Output is architectural.
    architecture = {
        "problem": top.get("title", "General SaaS productivity tool"),
        "stack": {
            "frontend": "Next.js 14 + shadcn/ui",
            "backend": "FastAPI (Python 3.12)",
            "database": "PostgreSQL 16 + SQLAlchemy",
            "cache": "Redis 7",
            "hosting": "Fly.io or Vercel + Supabase",
        },
        "features": ["authentication", "dashboard", "api", "webhooks", "monitoring"],
        "testing": {"framework": "pytest", "coverage_target": "90%", "e2e": "Playwright"},
        "ci_cd": "GitHub Actions",
        "security": ["OWASP Top 10 scan via bandit+safety", "Dependabot enabled", "pre-commit hooks"],
    }

    tracker.record_usage(
        TokenUsage(
            ts=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            agent_id="senior-engineer-agent",
            prompt_tokens=5000,
            completion_tokens=7000,
            total_tokens=12000,
            est_cost_usd=0.30,
            model="stub",
        )
    )
    return {
        "deployed_app_url": {"url": "https://demo.example.com", "status": "staged"},
        "architecture_docs": architecture,
        "source_files": [
            "app/main.py",
            "app/api/v1/routes.py",
            "app/models.py",
            "app/schemas.py",
            "app/db.py",
            "tests/conftest.py",
            "Dockerfile",
            "docker-compose.yml",
            ".github/workflows/ci.yml",
        ],
    }


def run_cybersecurity_agent(ctx: AgentContext, run_id: str, tracker: TokenTracker) -> Dict[str, Any]:
    """White-hat security audit of the built application."""
    app = ctx.get("senior-engineer", {}) or {}
    url = (app.get("deployed_app_url") or {}).get("url", "https://demo.example.com")

    findings = [
        {"severity": "high", "check": "SQL Injection", "status": "pass", "detail": "ORM in use, no raw SQL in routes"},
        {"severity": "high", "check": "XSS", "status": "pass", "detail": "React auto-escapes, CSP header set"},
        {"severity": "high", "check": "Authentication Bypass", "status": "pass", "detail": "OAuth2 + RBAC enforced"},
        {"severity": "medium", "check": "CORS", "status": "warn", "detail": "Allowlist currently open; tighten before prod"},
        {"severity": "medium", "check": "Rate Limiting", "status": "pass", "detail": "SlowAPI middleware active"},
        {"severity": "low", "check": "Security Headers", "status": "pass", "detail": "Helmet-style headers configured"},
        {"severity": "low", "check": "Dependency CVEs", "status": "warn", "detail": "2 moderate CVEs in transitive deps; patch pending"},
    ]

    patches = [
        {"file": "app/cors.py", "change": "Restrict allow_origins to production domain"},
        {"file": "requirements.in", "change": "Pin and patch flagged transitive dependency"},
    ]

    tracker.record_usage(
        TokenUsage(
            ts=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            agent_id="cybersecurity-agent",
            prompt_tokens=3500,
            completion_tokens=4500,
            total_tokens=8000,
            est_cost_usd=0.20,
            model="stub",
        )
    )
    return {
        "target_url": url,
        "vulnerability_report": {"findings": findings, "summary": {"pass": 5, "warn": 2, "fail": 0}},
        "remediation_patches": patches,
        "compliance_summary": {"soc2_ready": True, "pci_dss_scope": "in-scope for payments module"},
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

AGENTS: Dict[str, Any] = {
    "lead-finder": run_lead_finder,
    "profile-optimizer": run_profile_optimizer,
    "project-manager": run_project_manager,
    "code-agent": run_code_agent,
    "qa-agent": run_qa_agent,
    "billing-agent": run_billing_agent,
    "collector-agent": run_collector_agent,
    "economics-agent": run_economics_agent,
    "allocator-agent": run_allocator_agent,
    "scraping-agent": run_scraping_agent,
    "senior-engineer-agent": run_senior_engineer_agent,
    "cybersecurity-agent": run_cybersecurity_agent,
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class SwarmRunner:
    def __init__(self, data_dir: str = "data", definitions_path: Optional[str] = None) -> None:
        self.engine = WorkflowEngine(data_dir=data_dir)
        self.tracker = TokenTracker(data_dir=data_dir)
        self.ctx = AgentContext()
        if definitions_path:
            p = Path(definitions_path)
            if p.exists():
                data = json.loads(p.read_text())
                self.default_flow: list = data.get("default_flow", list(AGENTS.keys()))

    def execute(self, run_id: str, agent_id: str) -> Dict[str, Any]:
        fn = AGENTS.get(agent_id)
        if not fn:
            raise AgentError(f"Unknown agent: {agent_id}")

        result = fn(self.ctx, run_id, self.tracker)

        # Publish the agent's output into the context for downstream agents.
        key = agent_id
        self.ctx.set(key, result)
        return result

    def run_step(self, run_id: str, agent_id: str) -> Dict[str, Any]:
        result = self.execute(run_id, agent_id)
        self.engine.record_agent_complete(run_id, agent_id, result)
        return result

    def run_all(self, run_id: str, flow: Optional[list] = None) -> Dict[str, Any]:
        chain = flow or getattr(self, "default_flow", list(AGENTS.keys()))
        summary: Dict[str, Any] = {}
        for agent_id in chain:
            result = self.run_step(run_id, agent_id)
            summary[agent_id] = result
        self.engine.complete_run(run_id)
        return summary


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Freelance Swarm Agent Runner (sandbox)")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run-step", help="Run a single agent step for a workflow run")
    run_p.add_argument("run_id")
    run_p.add_argument("agent_id")

    run_all_p = sub.add_parser("run-all", help="Run all agents in default_flow for a workflow run")
    run_all_p.add_argument("run_id")

    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    definitions = root / "agents" / "definitions.json"
    runner = SwarmRunner(data_dir=(root / "data").as_posix(), definitions_path=definitions.as_posix())

    if args.command == "run-step":
        result = runner.run_step(args.run_id, args.agent_id)
        print(json.dumps(result, indent=2, default=str))
    elif args.command == "run-all":
        result = runner.run_all(args.run_id)
        print(json.dumps(result, indent=2, default=str))
    else:
        parser.print_help()
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
