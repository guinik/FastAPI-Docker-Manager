from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, Float, UniqueConstraint,
    Boolean
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from uuid import uuid4

Base = declarative_base()

def gen_uuid():
    return str(uuid4())

class UploadedImageDB(Base):
    __tablename__ = "uploaded_images"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    filename = Column(String, nullable=False)
    path = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending / loaded / failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DockerImageDB(Base):
    __tablename__ = "docker_images"

    id = Column(String, primary_key=True, default=gen_uuid)
    uploaded_image_id = Column(
        String,
        ForeignKey("uploaded_images.id"),
        nullable=False,
        unique=True
    )
    name = Column(String, nullable=True)        # Docker image name
    tag = Column(String, nullable=True)         # Docker tag, e.g. "latest"
    docker_id = Column(String, nullable=False)  # sha256:...
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=False, nullable=False)  # NEW

class ContainerDB(Base):
    __tablename__ = "containers"

    id = Column(String, primary_key=True, default=gen_uuid)
    docker_image_id = Column(String, ForeignKey("docker_images.id"), nullable=True)
    image = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending / running / stopped / failed
    cpu_limit = Column(Float, default=0.5)
    memory_limit_mb = Column(Integer, default=128)
    internal_port = Column(Integer, default=80)
    exposed_port = Column(Integer, nullable=True)
    docker_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())