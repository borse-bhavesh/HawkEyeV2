from abc import ABC, abstractmethod
from typing import Optional, List
from threading import Lock

from app.services.evidence.models import Evidence


class EvidenceRepositoryError(Exception):
    """Base exception for Evidence repository errors."""
    pass


class EvidenceAlreadyExistsError(EvidenceRepositoryError):
    """Exception raised when attempting to save evidence with an ID that already exists."""
    pass


class EvidenceRepository(ABC):
    """Abstract interface for Evidence metadata storage."""
    
    @abstractmethod
    def save(self, evidence: Evidence) -> Evidence:
        pass

    @abstractmethod
    def get_by_id(self, evidence_id: str) -> Optional[Evidence]:
        pass

    @abstractmethod
    def list_by_event_id(self, event_id: str) -> List[Evidence]:
        pass

    @abstractmethod
    def list_by_assessment_id(self, assessment_id: str) -> List[Evidence]:
        pass

    @abstractmethod
    def delete(self, evidence_id: str) -> bool:
        pass


class InMemoryEvidenceRepository(EvidenceRepository):
    """In-memory implementation of EvidenceRepository for testing and development."""
    
    def __init__(self):
        self._storage: dict[str, Evidence] = {}
        # Simple lock to ensure thread-safety for deterministic behavior
        self._lock = Lock()
        
    def save(self, evidence: Evidence) -> Evidence:
        if evidence is None:
            raise ValueError("evidence cannot be None")
            
        if not evidence.evidence_id:
            raise ValueError("evidence_id cannot be empty")
            
        with self._lock:
            if evidence.evidence_id in self._storage:
                raise EvidenceAlreadyExistsError(f"Evidence with id {evidence.evidence_id} already exists")
                
            # Defensive copy for storage
            self._storage[evidence.evidence_id] = evidence.model_copy(deep=True)
            
        # Defensive copy for return
        return evidence.model_copy(deep=True)
        
    def get_by_id(self, evidence_id: str) -> Optional[Evidence]:
        if not evidence_id:
            return None
            
        with self._lock:
            stored = self._storage.get(evidence_id)
            if stored is None:
                return None
            return stored.model_copy(deep=True)
            
    def list_by_event_id(self, event_id: str) -> List[Evidence]:
        if not event_id:
            return []
            
        with self._lock:
            # Dictionaries in Python 3.7+ preserve insertion order
            return [
                ev.model_copy(deep=True) 
                for ev in self._storage.values() 
                if ev.event_id == event_id
            ]
            
    def list_by_assessment_id(self, assessment_id: str) -> List[Evidence]:
        if not assessment_id:
            return []
            
        with self._lock:
            return [
                ev.model_copy(deep=True) 
                for ev in self._storage.values() 
                if ev.assessment_id == assessment_id
            ]
            
    def delete(self, evidence_id: str) -> bool:
        if not evidence_id:
            return False
            
        with self._lock:
            if evidence_id in self._storage:
                del self._storage[evidence_id]
                return True
            return False
