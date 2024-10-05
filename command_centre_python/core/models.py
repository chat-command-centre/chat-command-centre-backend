from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ActionStep(BaseModel):
    description: str
    parameters: Dict[str, Any]


class ActionPlan(BaseModel):
    goal: str
    steps: List[ActionStep]
    considerations: Optional[List[str]] = None
    priority: Optional[int] = Field(
        default=1, ge=1, le=5
    )  # Priority from 1 (high) to 5 (low)
