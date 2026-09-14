from typing import List, FrozenSet
from pydantic import BaseModel, Field, field_validator, model_validator
import hashlib

from app.services.events.models import EventType
from app.services.risk.models import RiskLevel, Priority

class RiskEscalationRule(BaseModel):
    """
    Configuration mapping an existing risk assessment and an observable event pattern
    to an escalated risk and priority level.
    """
    rule_id: str = Field(default="")
    source_risk_level: RiskLevel
    source_priority: Priority
    required_event_types: FrozenSet[EventType]
    minimum_occurrences: int = Field(..., gt=0)
    correlation_window_seconds: float = Field(..., gt=0.0)
    target_risk_level: RiskLevel
    target_priority: Priority
    reason_template: str = Field(..., min_length=1)

    @model_validator(mode='after')
    def generate_rule_id(self):
        if not self.rule_id:
            types = "_".join(sorted([et.value for et in self.required_event_types]))
            content = f"esc_{self.source_risk_level.value}_{types}_{self.target_risk_level.value}_{self.reason_template}"
            self.rule_id = hashlib.md5(content.encode()).hexdigest()
        return self

    @field_validator("required_event_types")
    def validate_required_event_types(cls, v):
        if not v:
            raise ValueError("Escalation rule requires at least one EventType.")
        return v

class RiskEscalationPolicy(BaseModel):
    rules: List[RiskEscalationRule] = Field(default_factory=list)

    @classmethod
    def default(cls) -> "RiskEscalationPolicy":
        return cls(
            rules=[
                RiskEscalationRule(
                    source_risk_level=RiskLevel.HIGH,
                    source_priority=Priority.HIGH,
                    required_event_types=frozenset([EventType.LOITERING]),
                    minimum_occurrences=2,
                    correlation_window_seconds=60.0,
                    target_risk_level=RiskLevel.CRITICAL,
                    target_priority=Priority.CRITICAL,
                    reason_template="Configured policy escalates the assessment because the required loitering event pattern occurred at least twice within the configured correlation window."
                )
            ]
        )

class RiskDeescalationRule(BaseModel):
    """
    Configuration mapping an existing risk assessment and a quiet period of absent event types
    to a de-escalated risk and priority level.
    """
    rule_id: str = Field(default="")
    source_risk_level: RiskLevel
    source_priority: Priority
    absence_event_types: FrozenSet[EventType]
    quiet_period_seconds: float = Field(..., gt=0.0)
    target_risk_level: RiskLevel
    target_priority: Priority
    reason_template: str = Field(..., min_length=1)

    @model_validator(mode='after')
    def generate_rule_id(self):
        if not self.rule_id:
            types = "_".join(sorted([et.value for et in self.absence_event_types]))
            content = f"deesc_{self.source_risk_level.value}_{types}_{self.target_risk_level.value}_{self.reason_template}"
            self.rule_id = hashlib.md5(content.encode()).hexdigest()
        return self

    @field_validator("absence_event_types")
    def validate_absence_event_types(cls, v):
        if not v:
            raise ValueError("De-escalation rule requires at least one EventType.")
        return v

class RiskDeescalationPolicy(BaseModel):
    rules: List[RiskDeescalationRule] = Field(default_factory=list)

    @classmethod
    def default(cls) -> "RiskDeescalationPolicy":
        return cls(
            rules=[
                RiskDeescalationRule(
                    source_risk_level=RiskLevel.HIGH,
                    source_priority=Priority.HIGH,
                    absence_event_types=frozenset([EventType.LOITERING]),
                    quiet_period_seconds=60.0,
                    target_risk_level=RiskLevel.MEDIUM,
                    target_priority=Priority.MEDIUM,
                    reason_template="Configured policy de-escalates the assessment because the specified event type has not been observed during the configured quiet period."
                )
            ]
        )
