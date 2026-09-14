from typing import List, Dict
from collections import defaultdict

from app.services.events.models import Event
from app.services.risk.models import RiskAssessment, RiskAssessmentStatus, RiskLevel, Priority, EvidenceSourceType, RiskAssessmentEvidence
from app.services.risk.escalation import RiskEscalationPolicy, RiskDeescalationPolicy, RiskEscalationRule, RiskDeescalationRule

class RiskEscalationEngine:
    """
    Evaluates sequences of events against existing assessments to apply
    configured policy-based escalation and de-escalation logic.
    Stateless and decision-support oriented.
    """

    def __init__(self, escalation_policy: RiskEscalationPolicy = None, deescalation_policy: RiskDeescalationPolicy = None):
        self._escalation_policy = escalation_policy if escalation_policy is not None else RiskEscalationPolicy.default()
        self._deescalation_policy = deescalation_policy if deescalation_policy is not None else RiskDeescalationPolicy.default()

    def evaluate(self, assessments: List[RiskAssessment], events: List[Event]) -> List[RiskAssessment]:
        """
        Evaluates a batch of assessments against a batch of events.
        Produces updated assessments (if rules match) or the original assessments.
        """
        if not assessments:
            return []

        # Group events by track_id for efficient track-aware correlation
        track_events: Dict[int, List[Event]] = defaultdict(list)
        # Also map event_id to its track_id to resolve assessment track context
        event_to_track: Dict[str, int] = {}
        
        for event in events:
            if event.track_id is not None:
                track_events[event.track_id].append(event)
                event_to_track[event.event_id] = event.track_id

        results = []

        for assessment in assessments:
            # Resolved assessments represent completed workflows; do not mutate automatically
            if assessment.status == RiskAssessmentStatus.RESOLVED:
                results.append(assessment)
                continue

            # Determine relevant tracks for this assessment
            relevant_tracks = set()
            for eid in assessment.contributing_event_ids:
                if eid in event_to_track:
                    relevant_tracks.add(event_to_track[eid])

            escalated = False
            matched_assessments = []
            
            for rule in self._escalation_policy.rules:
                if assessment.risk_level != rule.source_risk_level or assessment.priority != rule.source_priority:
                    continue
                match_found = False
                for track_id in relevant_tracks:
                    if self._check_escalation_rule(rule, track_events[track_id]):
                        match_found = True
                        break
                if match_found:
                    evidence = RiskAssessmentEvidence(
                        source_type=EvidenceSourceType.ESCALATION,
                        policy_identifier=rule.rule_id,
                        contributing_event_ids=assessment.contributing_event_ids.copy(),
                        contributing_event_types=assessment.contributing_event_types.copy(),
                        explanation="Configured escalation policy pattern occurred within the correlation window.",
                        details={"correlation_window_seconds": rule.correlation_window_seconds, "minimum_occurrences": rule.minimum_occurrences}
                    )
                    matched_assessments.append(self._apply_escalation(assessment, rule.target_risk_level, rule.target_priority, rule.reason_template, evidence))
                    escalated = True

            if escalated:
                results.extend(matched_assessments)
                continue

            # 2. Evaluate De-escalation
            deescalated = False
            for rule in self._deescalation_policy.rules:
                if assessment.risk_level != rule.source_risk_level or assessment.priority != rule.source_priority:
                    continue
                
                # Check if all relevant tracks satisfy the quiet period.
                # If there are no relevant tracks in the events, we can't establish a quiet period.
                if not relevant_tracks:
                    continue
                    
                all_quiet = True
                for track_id in relevant_tracks:
                    if not self._check_deescalation_rule(rule, track_events[track_id], assessment):
                        all_quiet = False
                        break
                
                if all_quiet:
                    evidence = RiskAssessmentEvidence(
                        source_type=EvidenceSourceType.DEESCALATION,
                        policy_identifier=rule.rule_id,
                        contributing_event_ids=assessment.contributing_event_ids.copy(),
                        contributing_event_types=assessment.contributing_event_types.copy(),
                        explanation="Configured quiet-period policy condition met.",
                        details={"quiet_period_seconds": rule.quiet_period_seconds}
                    )
                    matched_assessments.append(self._apply_escalation(assessment, rule.target_risk_level, rule.target_priority, rule.reason_template, evidence))
                    deescalated = True

            if deescalated:
                results.extend(matched_assessments)
                continue

            # 3. No rules matched, retain original
            results.append(assessment)

        return results

    def _check_escalation_rule(self, rule: RiskEscalationRule, events: List[Event]) -> bool:
        relevant = [e for e in events if e.event_type in rule.required_event_types]
        if not relevant:
            return False
            
        relevant.sort(key=lambda x: x.timestamp_seconds)
        
        for i in range(len(relevant)):
            start_ts = relevant[i].timestamp_seconds
            group_ids = set()
            group_types = set()
            
            for j in range(i, len(relevant)):
                evt = relevant[j]
                if evt.timestamp_seconds - start_ts > rule.correlation_window_seconds:
                    break
                group_ids.add(evt.event_id)
                group_types.add(evt.event_type)
                
                if len(group_ids) >= rule.minimum_occurrences and group_types.issuperset(rule.required_event_types):
                    return True
        return False

    def _check_deescalation_rule(self, rule: RiskDeescalationRule, events: List[Event], assessment: RiskAssessment) -> bool:
        if not events:
            return False
            
        latest_supplied_ts = max(e.timestamp_seconds for e in events)
        
        # Relevant events are those matching absence types, OR contributing to the assessment
        absence_events = [e for e in events if e.event_type in rule.absence_event_types]
        baseline_events = [e for e in events if e.event_id in assessment.contributing_event_ids]
        
        relevant_events = absence_events + baseline_events
        if not relevant_events:
            return False
            
        latest_relevant_ts = max(e.timestamp_seconds for e in relevant_events)
        
        if latest_supplied_ts - latest_relevant_ts >= rule.quiet_period_seconds:
            return True
            
        return False

    def _apply_escalation(self, original: RiskAssessment, target_level: RiskLevel, target_priority: Priority, reason: str, evidence: RiskAssessmentEvidence) -> RiskAssessment:
        # Preserve core traceability and lifecycle status
        return RiskAssessment(
            event_id=original.event_id,
            contributing_event_ids=original.contributing_event_ids.copy(),
            contributing_event_types=original.contributing_event_types.copy(),
            status=original.status,
            risk_level=target_level,
            priority=target_priority,
            reason=reason,
            evidence=evidence
        )
