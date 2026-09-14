from typing import Dict, Any
import hashlib
from pydantic import BaseModel, Field, model_validator

from app.services.events.models import EventType
from app.services.risk.models import RiskLevel, Priority

class RiskPolicyRule(BaseModel):
    """
    Configuration mapping an EventType to its categorical risk and priority.
    Explicitly does NOT use numeric risk scores.
    """
    rule_id: str = Field(default="", description="Deterministic or unique rule identifier")
    risk_level: RiskLevel = Field(..., description="Configured categorical risk level")
    priority: Priority = Field(..., description="Configured operational priority")
    reason_template: str = Field(..., min_length=1, description="Factual basis for this assessment")

    @model_validator(mode='after')
    def generate_rule_id(self):
        if not self.rule_id:
            content = f"policy_{self.risk_level.value}_{self.priority.value}_{self.reason_template}"
            self.rule_id = hashlib.md5(content.encode()).hexdigest()
        return self

class RiskPolicy(BaseModel):
    """
    Configuration mapping every observable EventType to a RiskPolicyRule.
    """
    rules: Dict[EventType, RiskPolicyRule] = Field(..., description="Mapping of event types to policy rules")

    @model_validator(mode="after")
    def validate_complete_coverage(self) -> "RiskPolicy":
        missing = []
        for event_type in EventType:
            if event_type not in self.rules:
                missing.append(event_type.value)
        if missing:
            raise ValueError(f"RiskPolicy is missing rules for EventTypes: {missing}")
        return self

    @classmethod
    def default(cls) -> "RiskPolicy":
        """
        Provides a conservative, deterministic default policy.
        These are configuration baselines, not statements that behaviors are inherently dangerous.
        """
        rules = {
            EventType.TRACK_STARTED: RiskPolicyRule(
                risk_level=RiskLevel.LOW,
                priority=Priority.LOW,
                reason_template="Configured policy classifies TRACK_STARTED as LOW priority."
            ),
            EventType.TRACK_ENDED: RiskPolicyRule(
                risk_level=RiskLevel.LOW,
                priority=Priority.LOW,
                reason_template="Configured policy classifies TRACK_ENDED as LOW priority."
            ),
            EventType.ZONE_ENTRY: RiskPolicyRule(
                risk_level=RiskLevel.HIGH,
                priority=Priority.HIGH,
                reason_template="Configured policy classifies restricted-zone intrusion as HIGH priority."
            ),
            EventType.ZONE_EXIT: RiskPolicyRule(
                risk_level=RiskLevel.LOW,
                priority=Priority.LOW,
                reason_template="Configured policy classifies ZONE_EXIT as LOW priority."
            ),
            EventType.LOITERING: RiskPolicyRule(
                risk_level=RiskLevel.HIGH,
                priority=Priority.HIGH,
                reason_template="Configured policy classifies LOITERING for elevated review."
            ),
            EventType.RAPID_MOVEMENT: RiskPolicyRule(
                risk_level=RiskLevel.MEDIUM,
                priority=Priority.HIGH,
                reason_template="Configured policy prioritizes RAPID_MOVEMENT for prompt review."
            ),
            EventType.DIRECTION_CHANGE: RiskPolicyRule(
                risk_level=RiskLevel.MEDIUM,
                priority=Priority.MEDIUM,
                reason_template="Configured policy classifies DIRECTION_CHANGE for standard review."
            ),
            EventType.MULTIPLE_OBJECT_PROXIMITY: RiskPolicyRule(
                risk_level=RiskLevel.MEDIUM,
                priority=Priority.MEDIUM,
                reason_template="Configured policy classifies MULTIPLE_OBJECT_PROXIMITY for standard review."
            )
        }
        return cls(rules=rules)
