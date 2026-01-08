from pydantic import BaseModel, Field, model_validator
from uuid import UUID
from datetime import datetime
from typing import Literal, Optional


class ContainerCreateRequest(BaseModel):
    image: Optional[str] = Field(None, description="Docker image name, e.g. nginx:latest")
    image_id: Optional[UUID] = Field(None, description="UUID of uploaded Docker image")
    internal_port: int = 80
    host_port: Optional[int] = None
    cpu_limit: float = 0.5
    memory_limit_mb: int = 128

    @model_validator(mode="after")
    def validate_image_source(self):
        if self.image is None and self.image_id is None:
            raise ValueError("Either image or image_id must be provided")

        if self.image is not None and self.image_id is not None:
            raise ValueError("Provide only one of image or image_id")

        return self

class ContainerResponse(BaseModel):
    id: UUID
    image: str
    status: Literal["pending", "running", "stopped", "failed"]
    docker_image_id : Optional[UUID]
    exposed_port: Optional[int]
    created_at: datetime
