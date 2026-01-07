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
    id: UUID
    docker_id: str              # sha256:...
    uploaded_image_id: UUID
    name : str
    tag : str
    created_at: datetime
    is_active : bool
