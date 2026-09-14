from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from itertools import product
import uuid

from app.services.events.models import Event
from app.services.risk.models import RiskAssessment, EvidenceSourceType, RiskAssessmentEvidence
from app.services.risk.correlation import RiskCorrelationPolicy, RiskCorrelationRule

class RiskCorrelationEngine:
    """
    Evaluates groups of related observable Events under an explicit multi-event correlation policy.
    Generates combined RiskAssessment decision-support objects statelessly.
    """

    def __init__(self, policy: RiskCorrelationPolicy = None):
        """
        Initializes the engine with a specific correlation policy.
        If no policy is provided, the default policy is loaded.
        """
        self._policy = policy if policy is not None else RiskCorrelationPolicy.default()

    def correlate(self, events: List[Event]) -> List[RiskAssessment]:
        """
        Statelessly evaluates the supplied batch of events against the configured correlation policy.
        Tracks are evaluated independently.
        """
        if not events:
            return []

        # Group events by track_id
        # Events without a track_id cannot be confidently correlated to a specific entity.
        track_events: Dict[int, List[Event]] = defaultdict(list)
        for event in events:
            if event.track_id is not None:
                track_events[event.track_id].append(event)

        assessments: List[RiskAssessment] = []

        # Sort track keys to ensure deterministic processing order across tracks
        for track_id in sorted(track_events.keys()):
            events_for_track = track_events[track_id]
            
            # Evaluate each rule against this track's events
            for rule in self._policy.rules:
                matched_combo = self._find_rule_match(rule, events_for_track, self._policy.correlation_window_seconds)
                
                if matched_combo:
                    # Deterministically sort contributing events by ID for the assessment
                    sorted_combo = sorted(matched_combo, key=lambda e: e.event_id)
                    contributing_ids = [e.event_id for e in sorted_combo]
                    # We can use the rule's event types or the combo's event types (they are identical as sets)
                    # We'll map them from the sorted combo to remain perfectly traceable
                    contributing_types = [e.event_type for e in sorted_combo]
                    
                    # Generate deterministic composite event ID to prevent collision
                    comp_id = f"corr-{uuid.uuid5(uuid.NAMESPACE_OID, ''.join(contributing_ids))}"
                    composite_id = comp_id
                    match_events = sorted_combo
                    contributing_event_types = [e.event_type for e in match_events]

                    evidence = RiskAssessmentEvidence(
                        source_type=EvidenceSourceType.CORRELATION,
                        policy_identifier=rule.rule_id,
                        contributing_event_ids=contributing_ids,
                        contributing_event_types=contributing_event_types,
                        explanation=f"Configured correlation policy matched {len(contributing_ids)} distinct event types within the {self._policy.correlation_window_seconds}-second temporal window.",
                        details={"correlation_window_seconds": self._policy.correlation_window_seconds}
                    )

                    assessment = RiskAssessment(
                        event_id=composite_id,
                        contributing_event_ids=contributing_ids,
                        contributing_event_types=contributing_event_types,
                        risk_level=rule.risk_level,
                        priority=rule.priority,
                        reason=rule.reason_template,
                        evidence=evidence
                    )
                    assessments.append(assessment)

        return assessments

    def _find_rule_match(self, rule: RiskCorrelationRule, track_events: List[Event], window: float) -> Optional[Tuple[Event, ...]]:
        """
        Finds the best deterministic combination of events that satisfies the rule's required EventTypes
        within the configured correlation temporal window.
        """
        events_by_type = {}
        for req_type in rule.event_types:
            # Filter events of this specific required type
            type_events = [e for e in track_events if e.event_type == req_type]
            if not type_events:
                return None  # Missing at least one required type for this rule
            events_by_type[req_type] = type_events
            
        valid_combos = []
        # Cartesian product yields all possible combinations containing exactly one of each required type
        # We ensure a fixed iteration order of required types to guarantee determinism
        ordered_req_types = sorted(list(rule.event_types), key=lambda x: x.value)
        
        for combo in product(*[events_by_type[t] for t in ordered_req_types]):
            timestamps = [e.timestamp_seconds for e in combo]
            if max(timestamps) - min(timestamps) <= window:
                valid_combos.append(combo)
                
        if not valid_combos:
            return None
            
        # Tie-breaker to ensure absolute determinism if multiple combinations satisfy the rule
        def combo_key(combo):
            ts = [e.timestamp_seconds for e in combo]
            e_ids = sorted([e.event_id for e in combo])
            return (max(ts), min(ts), e_ids)
            
        return min(valid_combos, key=combo_key)
