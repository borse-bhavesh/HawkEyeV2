from pydantic import BaseModel, Field

class RiskDeduplicationPolicy(BaseModel):
    """
    Explicit configuration for risk assessment deduplication.
    """
    enabled: bool = Field(default=True, description="Whether deduplication is active.")
    include_risk_level: bool = Field(default=True, description="Include RiskLevel in identity calculation.")
    include_priority: bool = Field(default=True, description="Include Priority in identity calculation.")
