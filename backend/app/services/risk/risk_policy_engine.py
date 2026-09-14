from typing import List

from app.services.events.models import Event
from app.services.risk.config import RiskConfig
from app.services.risk.models import RiskAssessment, EvidenceSourceType, RiskAssessmentEvidence
from app.services.risk.risk_engine import RiskEngine
from app.services.risk.policy import RiskPolicy

class RiskPolicyEngine(RiskEngine):
    """
    Concrete implementation of RiskEngine that utilizes a static RiskPolicy
    to deterministically evaluate individual events without assigning numeric scores.
    """

    def __init__(self, config: RiskConfig, policy: RiskPolicy = None):
        """
        Initializes the engine with the overall config and specific risk policy.
        If no policy is provided, the default policy is loaded.
        """
        super().__init__(config)
        self._policy = policy if policy is not None else RiskPolicy.default()

    def assess(self, event: Event) -> RiskAssessment:
        """
        Maps a single observable event into a structured decision-support assessment.
        Does not mutate the input event.
        Returns deterministically based solely on the configured policy.
        """
        if event.event_type not in self._policy.rules:
            raise KeyError(f"Event type '{event.event_type}' has no configured risk policy rule.")
        
        rule = self._policy.rules[event.event_type]

        evidence = RiskAssessmentEvidence(
            source_type=EvidenceSourceType.POLICY,
            policy_identifier=rule.rule_id,
            contributing_event_ids=[event.event_id],
            contributing_event_types=[event.event_type],
            explanation=f"Configured policy rule assigned categorical assessment based on {event.event_type.value} observation."
        )

        return RiskAssessment(
            event_id=event.event_id,
            contributing_event_ids=[event.event_id],
            contributing_event_types=[event.event_type],
            risk_level=rule.risk_level,
            priority=rule.priority,
            reason=rule.reason_template,
            evidence=evidence
        )

    def assess_events(self, events: List[Event]) -> List[RiskAssessment]:
        """
        Evaluates a batch of events sequentially, preserving order.
        Produces exactly one RiskAssessment per Event.
        """
        return [self.assess(event) for event in events]
