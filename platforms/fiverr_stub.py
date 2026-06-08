"""Fiverr integration stub.

Designed as a lightweight, local-only double-click automation target. No network
I/O unless the runner explicitly sets simulate_network_errors=True.
"""

from __future__ import annotations

from typing import List, Optional

from platforms.base import JobPosting, PlatformClient, ProposalResult


class FiverrClient(PlatformClient):
    platform_name = "fiverr"

    def __init__(self, *, simulate_network_errors: bool = False) -> None:
        super().__init__(simulate_network_errors=simulate_network_errors)
        self._jobs: List[JobPosting] = [
            JobPosting(
                id="fiverr-1",
                title="Logo Design for SaaS",
                client_id="buyer-fiverr-1",
                budget_usd=250.0,
                description="Modern minimal logo needed for a B2B SaaS brand.",
                tags=["design", "branding", "logo"],
                platform=self.platform_name,
                raw={"package_count": 3},
            ),
            JobPosting(
                id="fiverr-2",
                title="Bot Automation for E-commerce",
                client_id="buyer-fiverr-2",
                budget_usd=600.0,
                description="Python bot that scrapes competitor prices.",
                tags=["python", "automation", "ecommerce"],
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
            raise RuntimeError("Simulated Fiverr network error")

        matches = [j for j in self._jobs if j.id == job_id]
        job = matches[0] if matches else None
        fee_pct = 0.20 if job else 0.0
        result = ProposalResult(
            job_id=job_id,
            proposal_id=f"fiverr-offer-{job_id}-{len(self.submitted) + 1}",
            status="submitted",
            platform_fee_pct=fee_pct,
            estimated_ai_cost_usd=0.95,
            message="Stub order/custom offer created locally.",
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
            "status": "active",
            "platform": self.platform_name,
            "title": job.title if job else None,
        }

    def get_client_info(self, client_id: str) -> Dict[str, Any]:
        return {
            "client_id": client_id,
            "platform": self.platform_name,
            "name": f"{client_id} (local stub)",
            "verified": True,
        }
