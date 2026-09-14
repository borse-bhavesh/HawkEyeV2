"""
Step 7.8 — Evidence Linking Service.

A small, deterministic, stateless service that produces a new Evidence
instance with the requested event_id / assessment_id association
applied, without mutating the original Evidence object.
"""
from typing import Optional

from app.services.evidence.models import Evidence


class EvidenceLinkingService:
    """
    Links an existing Evidence object to an event_id and/or assessment_id
    by producing a new Evidence instance with the association applied.

    This service does NOT:
    - create events or risk assessments
    - validate that the referenced event/assessment exists
    - mutate the input Evidence object
    - interact with media, storage, or databases
    """

    def link(
        self,
        evidence: Evidence,
        event_id: Optional[str] = None,
        assessment_id: Optional[str] = None,
    ) -> Evidence:
        if evidence is None:
            raise ValueError("evidence cannot be None")

        if event_id is not None and not event_id.strip():
            raise ValueError("event_id cannot be empty or whitespace")

        if assessment_id is not None and not assessment_id.strip():
            raise ValueError("assessment_id cannot be empty or whitespace")

        if not event_id and not assessment_id:
            raise ValueError(
                "At least one of event_id or assessment_id must be provided"
            )

        return evidence.model_copy(
            update={
                "event_id": event_id if event_id is not None else evidence.event_id,
                "assessment_id": assessment_id if assessment_id is not None else evidence.assessment_id,
            },
            deep=True,
        )
