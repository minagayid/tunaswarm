"""Runnable smoke tests for platform integration stubs."""

from __future__ import annotations

import json
import pathlib
import sys
import traceback

PLATFORMS_PATH = pathlib.Path(__file__).resolve().parents[2]
if str(PLATFORMS_PATH) not in sys.path:
    sys.path.insert(0, str(PLATFORMS_PATH))

from platforms.base import JobPosting
from platforms.fiverr_stub import FiverrClient
from platforms.toptal_stub import ToptalClient
from platforms.upwork_stub import UpworkClient


def run_case(name: str, fn) -> bool:
    print(f"\n[TEST] {name}")
    try:
        fn()
    except Exception:
        traceback.print_exc()
        print(f"[FAIL] {name}")
        return False
    print(f"[PASS] {name}")
    return True


def test_upwork_fetch_and_submit():
    client = UpworkClient()
    jobs = client.fetch_jobs(limit=5)
    assert jobs, "Expected at least one job from Upwork stub"
    assert isinstance(jobs[0], JobPosting)

    filtered = client.fetch_jobs(query="react", limit=2)
    assert len(filtered) == 1
    assert filtered[0].id == "upwork-1"

    result = client.submit_proposal(
        job_id="upwork-1",
        cover_note="Hello",
        bid_amount_usd=1000.0,
        billing_account="billing-1",
    )
    assert result.status == "submitted"
    assert result.proposal_id == "upwork-prop-upwork-1-1"
    assert result.platform_fee_pct == 0.10
    assert result.meta["cover_note_length"] == 5

    status = client.get_job_status("upwork-1")
    assert status["status"] == "open"


def test_fiverr_fetch_and_submit():
    client = FiverrClient()
    jobs = client.fetch_jobs(limit=10)
    assert len(jobs) == 2

    result = client.submit_proposal(job_id="fiverr-2", cover_note="I can help")
    assert result.status == "submitted"
    assert result.platform_fee_pct == 0.20
    assert result.meta["cover_note_length"] == len("I can help")

    info = client.get_client_info("buyer-fiverr-2")
    assert "buyer-fiverr-2" in info["name"]


def test_toptal_fetch_and_submit():
    client = ToptalClient()
    jobs = client.fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].platform == "toptal"

    result = client.submit_proposal(
        job_id="toptal-1",
        cover_note="Experienced architect",
        bid_amount_usd=7500.0,
    )
    assert result.status == "submitted"
    assert result.platform_fee_pct == 0.0

    info = client.get_job_status("toptal-1")
    assert info["status"] == "invite_only"


def test_simulated_network_errors():
    upwork = UpworkClient(simulate_network_errors=True)
    fiverr = FiverrClient(simulate_network_errors=True)
    toptal = ToptalClient(simulate_network_errors=True)

    for client in (upwork, fiverr, toptal):
        try:
            client.submit_proposal("any-id", "note")
        except RuntimeError as exc:
            assert "Simulated" in str(exc)


def test_summary_json_output():
    engine = type("Engine", (), {"data_dir": None})()
    # Use the existing workflow engine import path if reachable

    results = {
        "upwork": [j.to_dict() if hasattr(j, "to_dict") else j.__dict__ for j in UpworkClient().fetch_jobs()],
        "fiverr": [j.__dict__ for j in FiverrClient().fetch_jobs()],
        "toptal": [j.__dict__ for j in ToptalClient().fetch_jobs()],
    }
    print(json.dumps(results, indent=2, default=str))


def main() -> int:
    cases = [
        ("upwork_fetch_and_submit", test_upwork_fetch_and_submit),
        ("fiverr_fetch_and_submit", test_fiverr_fetch_and_submit),
        ("toptal_fetch_and_submit", test_toptal_fetch_and_submit),
        ("simulated_network_errors", test_simulated_network_errors),
        ("summary_json_output", test_summary_json_output),
    ]

    results = [run_case(name, fn) for name, fn in cases]
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\nRESULTS: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
