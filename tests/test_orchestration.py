"""Tests for workflow engine lifecycle and failure-safe runner behaviour."""
from __future__ import annotations

import pytest

from orchestration.runner import AgentError, SwarmRunner
from orchestration.workflow_engine import WorkflowEngine


@pytest.fixture
def engine(tmp_path):
    return WorkflowEngine(data_dir=str(tmp_path))


@pytest.fixture
def runner(tmp_path):
    return SwarmRunner(data_dir=str(tmp_path))


def test_list_runs_orders_newest_first(engine):
    engine.start_run("run-a", total_steps=3)
    engine.start_run("run-b", total_steps=3)
    runs = engine.list_runs()
    assert [r.id for r in runs] == ["run-b", "run-a"]


def test_resume_run_reopens_failed_run(engine):
    engine.start_run("run-x", total_steps=3)
    engine.fail_run("run-x", "qa-agent", "boom")
    assert engine.get_run("run-x").status == "failed"
    resumed = engine.resume_run("run-x", "qa-agent")
    assert resumed.status == "running"
    assert resumed.finished_at is None


def test_resume_completed_run_is_rejected(engine):
    engine.start_run("run-y", total_steps=1)
    engine.complete_run("run-y")
    with pytest.raises(ValueError):
        engine.resume_run("run-y")


def test_runner_default_flow_always_set(runner):
    assert runner.default_flow, "default_flow must exist even without definitions.json"


def test_run_all_marks_run_failed_instead_of_dangling(runner, monkeypatch):
    run_id = "run-fail"
    runner.engine.start_run(run_id, total_steps=2)

    def boom(ctx, run_id, tracker):
        raise RuntimeError("agent exploded")

    monkeypatch.setitem(
        __import__("orchestration.runner", fromlist=["AGENTS"]).AGENTS, "lead-finder", boom
    )
    summary = runner.run_all(run_id, flow=["lead-finder", "qa-agent"])
    assert summary["_failed_at"] == "lead-finder"
    assert runner.engine.get_run(run_id).status == "failed"
    # qa-agent must not have run after the failure
    assert "qa-agent" not in summary


def test_run_all_completes_run(runner):
    run_id = "run-ok"
    runner.engine.start_run(run_id, total_steps=2)
    summary = runner.run_all(run_id, flow=["lead-finder", "qa-agent"])
    assert "_failed_at" not in summary
    assert runner.engine.get_run(run_id).status == "completed"


def test_run_step_unknown_agent_raises(runner):
    runner.engine.start_run("run-z", total_steps=1)
    with pytest.raises(AgentError):
        runner.run_step("run-z", "no-such-agent")


def test_resume_reruns_failing_agent_then_rest(runner):
    run_id = "run-resume"
    runner.engine.start_run(run_id, total_steps=3)
    runner.default_flow = ["lead-finder", "qa-agent", "billing-agent"]
    runner.engine.fail_run(run_id, "qa-agent", "flaky")
    summary = runner.resume(run_id, "qa-agent")
    assert set(summary) == {"qa-agent", "billing-agent"}
    assert runner.engine.get_run(run_id).status == "completed"
