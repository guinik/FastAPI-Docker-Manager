from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Literal, Optional


class ContainerCreateRequest(BaseModel):
    image: str = Field(..., example="nginx:latest")
    internal_port: int = Field(..., gt=0, lt=65536)
    cpu_limit: float = Field(..., gt=0)
    memory_limit_mb: int = Field(..., gt=0)


class ContainerResponse(BaseModel):
    id: UUID
    image: str
    status: Literal["pending", "running", "stopped", "failed"]
    exposed_port: Optional[int]
    created_at: datetime
