"""Base classes and shared types for freelance platform integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class JobPosting:
    id: str
    title: str
    client_id: Optional[str] = None
    budget_usd: Optional[float] = None
    description: str = ""
    tags: List[str] = field(default_factory=list)
    platform: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProposalResult:
    job_id: str
    proposal_id: Optional[str] = None
    status: str = "submitted"
    platform_fee_pct: float = 0.0
    estimated_ai_cost_usd: float = 0.0
    message: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


class PlatformClient(ABC):
    """Lightweight integration stub for a freelance platform.

    Subclasses must implement platform-specific fetch/job handling,
    but all interactions are local unless explicitly configured to
    enable network usage elsewhere.
    """

    platform_name: str = "base"

    def __init__(self, *, simulate_network_errors: bool = False) -> None:
        self.simulate_network_errors = simulate_network_errors
        self.submitted: Dict[str, ProposalResult] = {}

    @abstractmethod
    def fetch_jobs(self, query: str = "", *, limit: int = 10) -> List[JobPosting]:
        """Return a list of local job postings, optionally filtered by query."""

    @abstractmethod
    def submit_proposal(
        self,
        job_id: str,
        cover_note: str,
        *,
        bid_amount_usd: Optional[float] = None,
        billing_account: Optional[str] = None,
    ) -> ProposalResult:
        """Record a proposal submission locally and return the result stub."""

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Return any locally stored status for a job. Defaults to unknown."""
        return {"job_id": job_id, "status": "unknown", "platform": self.platform_name}

    def get_client_info(self, client_id: str) -> Dict[str, Any]:
        """Return local placeholder client info."""
        return {"client_id": client_id, "platform": self.platform_name, "name": "Local Client"}
