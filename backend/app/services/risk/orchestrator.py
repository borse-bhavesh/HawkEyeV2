from typing import List, Optional

from app.services.events.models import Event
from app.services.risk.config import RiskConfig
from app.services.risk.models import RiskAssessment
from app.services.risk.risk_policy_engine import RiskPolicyEngine
from app.services.risk.correlation_engine import RiskCorrelationEngine
from app.services.risk.escalation_engine import RiskEscalationEngine
from app.services.risk.deduplication_engine import RiskDeduplicationEngine

class RiskOrchestrator:
    """
    Coordinates the execution of all risk intelligence engines.
    Maintains engine state for exactly one video processing run.
    """

    def __init__(
        self,
        config: RiskConfig,
        policy_engine: Optional[RiskPolicyEngine] = None,
        correlation_engine: Optional[RiskCorrelationEngine] = None,
        escalation_engine: Optional[RiskEscalationEngine] = None,
        deduplication_engine: Optional[RiskDeduplicationEngine] = None,
    ):
        self.config = config
        
        # Instantiate engines bound to this processing run
        self.policy_engine = policy_engine or RiskPolicyEngine(config)
        self.correlation_engine = correlation_engine or RiskCorrelationEngine()
        self.escalation_engine = escalation_engine or RiskEscalationEngine()
        self.deduplication_engine = deduplication_engine or RiskDeduplicationEngine()

    def process_events(self, events: List[Event]) -> List[RiskAssessment]:
        """
        Produce risk assessments from a chronological list of events.
        Execution order guarantees that base assessments are correlated, 
        then escalated, then deduplicated.
        """
        if not self.config.enabled or not events:
            return []

        # 1. Base Policy Assessment
        # RiskPolicyEngine validates coverage for all EventTypes natively, so it
        # processes all incoming events deterministically.
        base_assessments = self.policy_engine.assess_events(events)

        # 2. Correlation
        correlated_assessments = self.correlation_engine.correlate(events)
        
        # Combine baseline and correlated assessments deterministically
        all_assessments = base_assessments + correlated_assessments

        # 3. Escalation / De-escalation
        escalated_assessments = self.escalation_engine.evaluate(all_assessments, events)

        # 4. Deduplication
        # Final pass ensures duplicate logic instances generated across frames
        # are mapped cleanly to exactly one unified output representation.
        final_assessments = self.deduplication_engine.deduplicate(escalated_assessments)

        return final_assessments
