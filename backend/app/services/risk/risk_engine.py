from abc import ABC, abstractmethod
from typing import List

from app.services.events.models import Event
from app.services.risk.models import RiskAssessment
from app.services.risk.config import RiskConfig

class RiskEngine(ABC):
    """
    Abstract interface for evaluating observable events and producing structured
    decision-support assessments (Risk/Priority).
    
    The engine explicitly does NOT determine criminality, intent, or autonomous action.
    """
    
    def __init__(self, config: RiskConfig):
        self.config = config
        
    @abstractmethod
    def assess(self, event: Event) -> RiskAssessment:
        """
        Evaluate an event and return its risk and priority assessment.
        Not implemented in the abstract base class.
        """
        pass

    @abstractmethod
    def assess_events(self, events: List[Event]) -> List[RiskAssessment]:
        """
        Evaluate a batch of events and return their assessments.
        Not implemented in the abstract base class.
        """
        pass
