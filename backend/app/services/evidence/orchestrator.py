from typing import List, Optional, Dict
import uuid

from app.services.events.models import Event
from app.services.risk.models import RiskAssessment
from app.services.evidence.models import Evidence, EvidenceType, EvidenceSource, FrameEvidence
from app.services.evidence.linker import EvidenceLinkingService


class EvidenceOrchestrator:
    """
    Coordinates metadata-only evidence generation for events and risks 
    within a single processing run using Phase 7 components.
    """

    def __init__(self, source_id: str, linker: Optional[EvidenceLinkingService] = None):
        self.source_id = source_id
        self.linker = linker or EvidenceLinkingService()

    def process(self, events: List[Event], risks: List[RiskAssessment]) -> List[Evidence]:
        all_evidence: List[Evidence] = []
        
        # Maps event_id -> List[Evidence] produced for that event.
        # Note: We store a list because an event could potentially have multiple 
        # pieces of evidence, but we only create one FrameEvidence here.
        event_evidence_map: Dict[str, Evidence] = {}

        # 1. Generate Frame Evidence for Events
        for event in events:
            # Generate deterministic FrameEvidence using factual event metadata
            frame_metadata = FrameEvidence(
                frame_number=event.frame_number,
                timestamp_seconds=event.timestamp_seconds
            )
            
            base_ev = Evidence(
                evidence_id=f"ev-{uuid.uuid4()}",
                evidence_type=EvidenceType.FRAME,
                source=EvidenceSource(source_id=self.source_id, source_type="video"),
                frame=frame_metadata,
                event_id=event.event_id
            )
            
            # Link it to the event using Phase 7 service
            linked_ev = self.linker.link(base_ev, event_id=event.event_id)
            
            all_evidence.append(linked_ev)
            event_evidence_map[event.event_id] = linked_ev

        # 2. Link Evidence for Risk Assessments
        for risk in risks:
            # We attempt to find the primary contributing event evidence
            for eid in risk.contributing_event_ids:
                if eid in event_evidence_map:
                    base_ev = event_evidence_map[eid]
                    
                    if base_ev.assessment_id is None:
                        # Direct 1:1 update in-place within the returned list via replacement.
                        # Wait, we must replace it in all_evidence.
                        # We use linker to link the assessment id (this preserves evidence_id)
                        new_linked_ev = self.linker.link(base_ev, assessment_id=risk.event_id) # risk.event_id is the Phase 6 assessment identifier
                        
                        # Replace the old evidence with the newly linked one
                        idx = all_evidence.index(base_ev)
                        all_evidence[idx] = new_linked_ev
                        event_evidence_map[eid] = new_linked_ev
                    else:
                        # The Evidence already belongs to another RiskAssessment.
                        # The Phase 7 Evidence schema only permits ONE assessment_id per Evidence object.
                        # Thus we must clone the evidence for the second RiskAssessment.
                        cloned_ev = Evidence(
                            evidence_id=f"ev-{uuid.uuid4()}",
                            evidence_type=base_ev.evidence_type,
                            source=base_ev.source,
                            frame=base_ev.frame,
                            video_segment=base_ev.video_segment,
                            event_id=base_ev.event_id
                        )
                        
                        # Use linker to link BOTH the original event AND the new assessment
                        linked_clone = self.linker.link(cloned_ev, event_id=base_ev.event_id, assessment_id=risk.event_id)
                        all_evidence.append(linked_clone)
                        
                    break # We just need to associate the risk with its primary evidence

        return all_evidence
