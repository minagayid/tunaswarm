"""Toptal integration stub.

Intentionally minimal: Toptal is invite-driven, so this stub covers a basic
client abstraction without realistic job feeds. All behavior is local-only.
"""

from __future__ import annotations

from typing import List, Optional

from platforms.base import JobPosting, PlatformClient, ProposalResult


class ToptalClient(PlatformClient):
    platform_name = "toptal"

    def __init__(self, *, simulate_network_errors: bool = False) -> None:
        super().__init__(simulate_network_errors=simulate_network_errors)
        self._jobs: List[JobPosting] = [
            JobPosting(
                id="toptal-1",
                title="Enterprise Architect Contract",
                client_id="company-toptal-1",
                budget_usd=8500.0,
                description="Long-term contract for architecture review.",
                tags=["architecture", "enterprise", "review"],
                platform=self.platform_name,
                raw={"duration_months": 6},
            )
        ]

    def fetch_jobs(self, query: str = "", *, limit: int = 10) -> List[JobPosting]:
        q = query.lower()
        matches = [j for j in self._jobs if not q or q in j.title.lower() or any(q in t.lower() for t in j.tags)]
        return matches[: max(limit, 0)]

    def submit_proposal(
        self,
        job_id: str,
        cover_note: str,
        *,
        bid_amount_usd: Optional[float] = None,
        billing_account: Optional[str] = None,
    ) -> ProposalResult:
        if self.simulate_network_errors:
            raise RuntimeError("Simulated Toptal network error")

        matches = [j for j in self._jobs if j.id == job_id]
        job = matches[0] if matches else None
        fee_pct = 0.0 if job else 0.0
        result = ProposalResult(
            job_id=job_id,
            proposal_id=f"toptal-app-{job_id}-{len(self.submitted) + 1}",
            status="submitted",
            platform_fee_pct=fee_pct,
            estimated_ai_cost_usd=2.10,
            message="Stub application recorded locally.",
            meta={
                "bid_amount_usd": bid_amount_usd,
                "billing_account": billing_account,
                "cover_note_length": len(cover_note),
            },
        )
        self.submitted[job_id] = result
        return result

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        job = next((j for j in self._jobs if j.id == job_id), None)
        return {
            "job_id": job_id,
            "status": "invite_only",
            "platform": self.platform_name,
            "title": job.title if job else None,
        }

    def get_client_info(self, client_id: str) -> Dict[str, Any]:
        return {
            "client_id": client_id,
            "platform": self.platform_name,
            "name": f"{client_id} (local stub)",
            "screening_passed": False,
        }
