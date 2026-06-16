"""Sandbox tests: verify every agent in definitions.json has a working runner."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestration.runner import AGENTS, SwarmRunner, AgentContext
from orchestration.workflow_engine import WorkflowEngine
from tracking.token_tracker import TokenTracker


@pytest.fixture()
def definitions_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "agents" / "definitions.json")


@pytest.fixture()
def fresh_data_dir(tmp_path: Path, definitions_path: str) -> str:
    d = tmp_path / "data"
    d.mkdir()
    # init the tracker + workflow db in the temp dir
    TokenTracker(data_dir=str(d))
    WorkflowEngine(data_dir=str(d))
    return str(d)


class TestDefinitions:
    def test_definitions_load(self, definitions_path: str):
        with open(definitions_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "agents" in data
        assert "default_flow" in data
        assert len(data["agents"]) >= 21

    def test_default_flow_matches_registry(self, definitions_path: str):
        with open(definitions_path, encoding="utf-8") as f:
            data = json.load(f)
        for aid in data["default_flow"]:
            assert aid in AGENTS, f"Agent {aid} missing in runner registry"

    def test_no_duplicate_ids(self, definitions_path: str):
        with open(definitions_path, encoding="utf-8") as f:
            data = json.load(f)
        ids = [a["id"] for a in data["agents"]]
        assert len(ids) == len(set(ids)), f"Duplicate agent IDs: {ids}"


class TestAgentRunners:
    def test_each_agent_runs(self, fresh_data_dir: str, definitions_path: str):
        SwarmRunner(data_dir=fresh_data_dir, definitions_path=definitions_path)
        ctx = AgentContext()
        for agent_id, fn in AGENTS.items():
            result = fn(ctx, f"run-{agent_id}", TokenTracker(data_dir=fresh_data_dir))
            assert isinstance(result, dict), f"{agent_id}: expected dict, got {type(result).__name__}"
            assert result, f"{agent_id}: returned empty dict"
            # Every agent result should include something we can inspect
            keys = list(result.keys())
            assert keys, f"{agent_id}: dict has no keys"

    def test_full_twenty_one_agent_flow(self, definitions_path: str, fresh_data_dir: str):
        runner = SwarmRunner(data_dir=fresh_data_dir, definitions_path=definitions_path)
        ctx = AgentContext()
        run_id = "sandbox-flow-test"
        tracker = TokenTracker(data_dir=fresh_data_dir)

        # The executor flips the same stage key, but we want to simulate context passing
        outputs: dict = {}
        chain = runner.default_flow
        for aid in chain:
            res = AGENTS[aid](ctx, run_id, tracker)
            outputs[aid] = res
            ctx.set(aid, res)

        assert len(outputs) == 21, f"Expected 21 agents, ran {len(outputs)}"
        # executive agents should produce strategy/operations/people/legal outputs
        assert "strategic_plan" in outputs["ceo-agent"], "ceo-agent missing strategic plan"
        assert "financial_plan" in outputs["cfo-agent"], "cfo-agent missing financial plan"
        assert "operational_plan" in outputs["coo-agent"], "coo-agent missing operational plan"
        assert "marketing_strategy" in outputs["cmo-agent"], "cmo-agent missing marketing strategy"
        assert "hiring_plan" in outputs["chro-agent"], "chro-agent missing hiring plan"
        assert "contract_reviews" in outputs["general-counsel-agent"], "general-counsel-agent missing contract reviews"
        assert "deployed_app_url" in outputs["software-engineer-agent"], "software-engineer-agent missing deploy URL"
        # economics and allocator should produce real-looking keys
        assert "revenue_usd" in outputs["economics-agent"], "economics-agent missing revenue"
        assert "net_profit_usd" in outputs["allocator-agent"], "allocator-agent missing net_profit"
        # crypto and domain agents should produce profit data
        assert "trade_executions" in outputs["crypto-stock-agent"], "crypto agent missing trade executions"
        assert "flip_profit_report" in outputs["domain-flip-agent"], "domain agent missing profit report"
