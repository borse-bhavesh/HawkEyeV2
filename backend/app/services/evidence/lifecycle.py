"""
Step 7.10 — Evidence Lifecycle Service.

A stateless, deterministic service that validates Evidence objects
against the existing Evidence model invariants.
"""
from typing import Iterable

from pydantic import ValidationError

from app.services.evidence.models import Evidence


class EvidenceValidationError(ValueError):
    """Raised when an Evidence object fails structural validation."""
    pass


class EvidenceLifecycleService:
    """
    Validates existing Evidence objects against the Evidence model invariants.

    This service does NOT:
    - create, modify, or delete evidence
    - access databases, repositories, or filesystems
    - mutate input Evidence objects
    - introduce new business rules beyond the Evidence model
    """

    def validate(self, evidence: Evidence) -> Evidence:
        """
        Validate a single Evidence object.

        Returns the same logical evidence if valid.
        Raises ValueError/EvidenceValidationError if invalid.
        """
        if evidence is None:
            raise ValueError("evidence cannot be None")

        try:
            # Re-validate by round-tripping through the model to ensure
            # all Pydantic invariants hold, even if the object was
            # constructed via object.__setattr__ or other bypasses.
            validated = Evidence.model_validate(evidence.model_dump())
        except ValidationError as e:
            raise EvidenceValidationError(
                f"Evidence validation failed: {e}"
            ) from e

        return validated

    def validate_many(self, evidence: Iterable[Evidence]) -> list[Evidence]:
        """
        Validate a collection of Evidence objects.

        Preserves input order. Returns validated copies.
        Raises on the first invalid Evidence encountered.
        """
        if evidence is None:
            raise ValueError("evidence collection cannot be None")

        results: list[Evidence] = []
        for ev in evidence:
            results.append(self.validate(ev))

        return results
