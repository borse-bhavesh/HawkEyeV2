from pydantic import BaseModel, Field

class RiskConfig(BaseModel):
    """
    Configuration for Risk and Priority assessment policies.
    Independent from Detection, Tracking, and Event Intelligence configurations.
    """
    enabled: bool = Field(default=True, description="Whether the risk engine is enabled")
