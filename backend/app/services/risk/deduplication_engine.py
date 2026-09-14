import hashlib
import json
from typing import List, Set

from app.services.risk.models import RiskAssessment
from app.services.risk.deduplication import RiskDeduplicationPolicy

class RiskDeduplicationEngine:
    """
    Stateless engine to deduplicate RiskAssessments based on a configured policy.
    Identifies duplicate logical assessments and retains only the first occurrence,
    preserving input ordering without modifying original objects or events.
    """

    def __init__(self, policy: RiskDeduplicationPolicy = None):
        self._policy = policy if policy is not None else RiskDeduplicationPolicy()

    def deduplicate(self, assessments: List[RiskAssessment]) -> List[RiskAssessment]:
        if not assessments or not self._policy.enabled:
            # Return a shallow copy to prevent external mutation issues, preserving ordering.
            return list(assessments)

        seen_identities: Set[str] = set()
        unique_assessments: List[RiskAssessment] = []

        for assessment in assessments:
            identity = self._calculate_identity(assessment)
            if identity not in seen_identities:
                seen_identities.add(identity)
                unique_assessments.append(assessment)

        return unique_assessments

    def _calculate_identity(self, assessment: RiskAssessment) -> str:
        """
        Creates a deterministic logical identity string using hashlib for deduplication.
        It is NOT a cryptographic security mechanism.
        """
        # Normalize event IDs and types to be order-independent
        sorted_event_ids = sorted(assessment.contributing_event_ids)
        sorted_event_types = sorted([et.value for et in assessment.contributing_event_types])

        components = {
            "event_id": assessment.event_id,
            "contributing_event_ids": sorted_event_ids,
            "contributing_event_types": sorted_event_types,
        }

        if self._policy.include_risk_level:
            components["risk_level"] = assessment.risk_level.value

        if self._policy.include_priority:
            components["priority"] = assessment.priority.value

        # Serialize to a deterministic JSON string
        canonical_str = json.dumps(components, sort_keys=True)
        
        # Digest purely for identity matching
        return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()
