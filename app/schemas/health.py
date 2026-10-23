from typing import Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    status: str = Field("healthy", description="healthy | degraded | unhealthy")
    project: str
    version: str
    database: bool
    storage: Dict[str, Any]
    inference_backend: str
    timestamp: datetime
