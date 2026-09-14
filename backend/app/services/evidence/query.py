"""
Step 7.9 — Evidence Query Service.

A stateless, deterministic service that filters a sequence of Evidence
objects by optional criteria using AND semantics.
"""
from typing import Iterable, Optional

from app.services.evidence.models import Evidence, EvidenceType


class EvidenceQueryService:
    """
    Filters existing Evidence objects without mutating them.

    This service does NOT:
    - access databases or repositories
    - load media or scan filesystems
    - mutate input Evidence objects
    - deduplicate results
    """

    def query(
        self,
        evidence: Iterable[Evidence],
        *,
        evidence_type: Optional[EvidenceType] = None,
        source_id: Optional[str] = None,
        source_type: Optional[str] = None,
        event_id: Optional[str] = None,
        assessment_id: Optional[str] = None,
    ) -> list[Evidence]:
        if evidence is None:
            raise ValueError("evidence collection cannot be None")

        if source_id is not None and not source_id.strip():
            raise ValueError("source_id filter cannot be empty or whitespace")

        if source_type is not None and not source_type.strip():
            raise ValueError("source_type filter cannot be empty or whitespace")

        if event_id is not None and not event_id.strip():
            raise ValueError("event_id filter cannot be empty or whitespace")

        if assessment_id is not None and not assessment_id.strip():
            raise ValueError("assessment_id filter cannot be empty or whitespace")

        results: list[Evidence] = []
        for ev in evidence:
            if evidence_type is not None and ev.evidence_type != evidence_type:
                continue
            if source_id is not None and ev.source.source_id != source_id:
                continue
            if source_type is not None and ev.source.source_type != source_type:
                continue
            if event_id is not None and ev.event_id != event_id:
                continue
            if assessment_id is not None and ev.assessment_id != assessment_id:
                continue
            results.append(ev)

        return results
