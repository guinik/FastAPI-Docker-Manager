from uuid import uuid4, UUID
from datetime import datetime
from dataclasses import dataclass, field
@dataclass
class Container:
    id: UUID
    image: str
    status: str
    cpu_limit: float
    memory_limit_mb: int
    internal_port: int = 80  # nginx default
    exposed_port: int | None = None
    docker_id: str | None = None
    docker_image_id : str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)