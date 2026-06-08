"""Upwork integration stub.

Defaults to local, no network behavior. Provides small, in-memory datasets
that keep the system runnable offline.
"""

from __future__ import annotations

from typing import List, Optional

from platforms.base import JobPosting, PlatformClient, ProposalResult


class UpworkClient(PlatformClient):
    platform_name = "upwork"

    def __init__(self, *, simulate_network_errors: bool = False) -> None:
        super().__init__(simulate_network_errors=simulate_network_errors)
        self._jobs: List[JobPosting] = [
            JobPosting(
                id="upwork-1",
                title="React Dashboard MVP",
                client_id="client-upwork-1",
                budget_usd=1200.0,
                description="Build a small analytics dashboard with React.",
                tags=["react", "typescript", "dashboard"],
                platform=self.platform_name,
                raw={"fixed_price": True},
            ),
            JobPosting(
                id="upwork-2",
                title="Python Data Pipeline Maintenance",
                client_id="client-upwork-2",
                budget_usd=800.0,
                description="Maintain weekly ETL pipeline.",
                tags=["python", "etl", "data"],
                platform=self.platform_name,
                raw={"hourly": False},
            ),
            JobPosting(
                id="upwork-3",
                title="Technical Writer for SDK Docs",
                client_id="client-upwork-3",
                budget_usd=400.0,
                description="Write Getting Started docs for an API SDK.",
                tags=["writing", "docs", "sdk"],
                platform=self.platform_name,
                raw={},
            ),
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
            raise RuntimeError("Simulated Upwork network error")

        matches = [j for j in self._jobs if j.id == job_id]
        job = matches[0] if matches else None
        fee_pct = 0.10 if job else 0.0
        result = ProposalResult(
            job_id=job_id,
            proposal_id=f"upwork-prop-{job_id}-{len(self.submitted) + 1}",
            status="submitted",
            platform_fee_pct=fee_pct,
            estimated_ai_cost_usd=1.25,
            message="Stub submission accepted locally.",
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
            "status": "open",
            "platform": self.platform_name,
            "title": job.title if job else None,
        }

    def get_client_info(self, client_id: str) -> Dict[str, Any]:
        return {
            "client_id": client_id,
            "platform": self.platform_name,
            "name": f"{client_id} (local stub)",
            "country": "XX",
        }
