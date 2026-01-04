from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime


@dataclass
class UploadedImage:
    id: UUID = field(default_factory=uuid4)
    filename: str = ""
    path: str = ""          # saved .tar path
    status: str = "pending" # pending / loaded / failed
    created_at: datetime = field(default_factory=datetime.utcnow)
    
@dataclass
class DockerImage:
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    tag: str = "latest"
    docker_id: str | None = None
    status: str = "loaded"  # loaded / failed
    created_at: datetime = field(default_factory=datetime.utcnow)
    uploaded_image_id: UUID | None = None  # ← add this