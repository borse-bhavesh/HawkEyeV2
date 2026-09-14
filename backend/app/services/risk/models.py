from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from pydantic import BaseModel, Field

from app.services.events.models import EventType

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskAssessmentStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

class EvidenceSourceType(str, Enum):
    POLICY = "POLICY"
    CORRELATION = "CORRELATION"
    ESCALATION = "ESCALATION"
    DEESCALATION = "DEESCALATION"

class RiskAssessmentEvidence(BaseModel):
    """
    Structured machine-readable evidence explaining a categorical assessment decision.
    """
    source_type: EvidenceSourceType = Field(..., description="Engine layer that produced the assessment")
    policy_identifier: str = Field(..., min_length=1, description="Deterministic identifier of the applied rule")
    contributing_event_ids: List[str] = Field(default_factory=list, description="Events explicitly matched by the rule")
    contributing_event_types: List[EventType] = Field(default_factory=list, description="EventTypes matched by the rule")
    explanation: str = Field(..., min_length=1, description="Factual, policy-based explanation")
    details: Dict[str, Any] = Field(default_factory=dict, description="Optional structured metrics supporting the rule")


class RiskAssessment(BaseModel):
    """
    Structured assessment derived from observable events.
    This model explicitly does not declare criminality, intent, or autonomous action.
    It serves strictly as decision-support for human review.
    """
    event_id: str = Field(..., min_length=1, description="Source event ID triggering the assessment")
    contributing_event_ids: List[str] = Field(default_factory=list, description="IDs of all contributing events")
    contributing_event_types: List[EventType] = Field(default_factory=list, description="Types of contributing events")
    risk_level: RiskLevel = Field(..., description="Normalized risk level assessed by policy")
    priority: Priority = Field(..., description="Operational urgency for human review")
    reason: str = Field(..., min_length=1, description="Human-readable explanation of the assessment")
    status: RiskAssessmentStatus = Field(default=RiskAssessmentStatus.OPEN, description="Lifecycle workflow status")
    evidence: Optional[RiskAssessmentEvidence] = Field(default=None, description="Structured policy explanation")

    def transition_to(self, new_status: RiskAssessmentStatus):
        if self.status == new_status:
            return

        valid_transitions = {
            RiskAssessmentStatus.OPEN: [RiskAssessmentStatus.ACKNOWLEDGED],
            RiskAssessmentStatus.ACKNOWLEDGED: [RiskAssessmentStatus.RESOLVED],
            RiskAssessmentStatus.RESOLVED: []
        }

        if new_status not in valid_transitions[self.status]:
            raise ValueError(f"Invalid lifecycle transition from {self.status.name} to {new_status.name}")

        self.status = new_status
