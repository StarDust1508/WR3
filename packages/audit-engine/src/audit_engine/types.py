from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

Network = Literal["ethereum", "base", "arbitrum", "bsc", "solana"]


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Finding(BaseModel):
    """A single security finding produced by one of the analyzers."""

    id: str
    title: str
    description: str
    severity: Severity
    source_engine: str  # "aderyn" | "wake" | "slither" | "medusa" | "trident" | "llm-agent"
    file: str | None = None
    line: int | None = None
    swc_id: str | None = None
    cwe_id: str | None = None
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    dismissed: bool = False
    dismissed_reason: str | None = None
    poc_path: str | None = None  # path to generated Foundry test
    poc_validated: bool = False
    metadata: dict = Field(default_factory=dict)


class ScoreAxis(BaseModel):
    name: str
    weight: float = Field(..., ge=0.0, le=1.0)
    # `score=None` means the axis isn't evaluated yet (weight should be 0).
    # We surface None instead of fake-neutral 80 so the renderer can show
    # "pending" honestly instead of padding the final score.
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    rationale: str


class AuditReport(BaseModel):
    """Full audit report. Persisted to DB + rendered as Markdown."""

    address: str
    network: Network
    score: float = Field(..., ge=0.0, le=100.0)
    tier: Literal["red", "yellow", "green", "blue"]
    axes: list[ScoreAxis]
    findings: list[Finding]
    engine_versions: dict[str, str] = Field(default_factory=dict)
    audit_duration_seconds: float | None = None
    # Optional on-chain metadata enrichment. Populated for Solana programs
    # via getAccountInfo (upgrade authority, executable, last upgrade slot)
    # and ignored for everything else. Loose dict — schema evolves with new
    # signals without forcing a migration of the report column.
    chain_metadata: dict = Field(default_factory=dict)
    disclaimer: str = (
        "AI-assisted audit results are best-effort and not a replacement for human review. "
        "wr3 provides no warranty. Liability is capped at the cost of the audit."
    )
