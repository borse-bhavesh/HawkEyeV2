from typing import List, FrozenSet
from pydantic import BaseModel, Field, field_validator, model_validator
import hashlib

from app.services.events.models import EventType
from app.services.risk.models import RiskLevel, Priority

class RiskCorrelationRule(BaseModel):
    """
    Configuration mapping a specific combination of EventTypes to its categorical risk and priority.
    """
    rule_id: str = Field(default="", description="Unique identifier for the rule")
    event_types: FrozenSet[EventType] = Field(..., description="Set of required EventTypes to trigger correlation")
    risk_level: RiskLevel = Field(..., description="Configured categorical risk level for the correlation")
    priority: Priority = Field(..., description="Configured operational priority for the correlation")
    reason_template: str = Field(..., min_length=1, description="Factual basis for this assessment")

    @model_validator(mode='after')
    def generate_rule_id(self):
        if not self.rule_id:
            types = "_".join(sorted([et.value for et in self.event_types]))
            content = f"corr_{types}_{self.risk_level.value}_{self.priority.value}_{self.reason_template}"
            self.rule_id = hashlib.md5(content.encode()).hexdigest()
        return self

    @field_validator("event_types")
    def validate_event_types_count(cls, v):
        if len(v) < 2:
            raise ValueError("A correlation rule requires at least two distinct EventTypes.")
        return v

class RiskCorrelationPolicy(BaseModel):
    """
    Configuration holding all active correlation rules and the temporal matching parameters.
    """
    rules: List[RiskCorrelationRule] = Field(default_factory=list, description="List of configured correlation rules")
    correlation_window_seconds: float = Field(default=30.0, gt=0.0, description="Maximum time between correlated events")

    @classmethod
    def default(cls) -> "RiskCorrelationPolicy":
        """
        Provides a conservative, deterministic default multi-event correlation policy.
        """
        return cls(
            rules=[
                RiskCorrelationRule(
                    event_types=frozenset([EventType.ZONE_ENTRY, EventType.LOITERING]),
                    risk_level=RiskLevel.HIGH,
                    priority=Priority.HIGH,
                    reason_template="Configured policy escalates review priority when a zone entry and subsequent loitering observation are correlated."
                ),
                RiskCorrelationRule(
                    event_types=frozenset([EventType.ZONE_ENTRY, EventType.RAPID_MOVEMENT]),
                    risk_level=RiskLevel.HIGH,
                    priority=Priority.HIGH,
                    reason_template="Configured policy escalates review priority when a zone entry and rapid-movement observations are correlated."
                ),
                RiskCorrelationRule(
                    event_types=frozenset([EventType.RAPID_MOVEMENT, EventType.DIRECTION_CHANGE]),
                    risk_level=RiskLevel.HIGH,
                    priority=Priority.HIGH,
                    reason_template="Configured policy escalates review priority when rapid movement and a direction-change observation are correlated."
                ),
                RiskCorrelationRule(
                    event_types=frozenset([EventType.MULTIPLE_OBJECT_PROXIMITY, EventType.LOITERING]),
                    risk_level=RiskLevel.HIGH,
                    priority=Priority.HIGH,
                    reason_template="Configured policy escalates review priority when proximity and loitering observations are correlated."
                )
            ]
        )
