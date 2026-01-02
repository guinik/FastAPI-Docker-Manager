# app/schemas/image.py
from pydantic import BaseModel
from uuid import UUID
from typing import Literal, Optional

# ---------------------------
# Uploaded Docker image schema
# ---------------------------
class UploadedImageResponse(BaseModel):
    id: UUID
    filename: str
    status: Literal["pending", "loaded", "failed"]

    class Config:
        json_schema_extra = {
            "example": {
                "id": "f3a0b8e7-1c2d-4b1a-9f3e-8d9a0c1a1b2c",
                "filename": "myimage.tar",
                "status": "pending"
            }
        }


# ---------------------------
# Docker-loaded image schema
# ---------------------------
class DockerImageResponse(BaseModel):
    id: UUID
    name: str
    tag: str
    docker_id: Optional[str] = None
    status: Literal["pending", "loaded", "failed"]

    class Config:
        json_schema_extra = {
            "example": {
                "id": "c1b2a3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
                "name": "myimage",
                "tag": "latest",
                "docker_id": "9a0b8c7d6e5f4a3b2c1d0e9f8a7b6c5d",
                "status": "loaded"
            }
        }
