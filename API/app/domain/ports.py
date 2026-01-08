from typing import Protocol, List
from uuid import UUID

from app.domain.container import Container
from app.domain.image import DockerImage, UploadedImage

class ContainerRepository(Protocol):
    async def create(self, container: Container) -> None: ...

    async def get(self, container_id: UUID) -> Container | None: ...

    async def list(self) -> List[Container]: ...

    async def update(
        self,
        container_id: UUID,
        *,
        status: str | None = None,
        docker_id: str | None = None,
        exposed_port: int | None = None,
    ) -> None: ...

    async def delete(self, container_id: UUID) -> None: ...

class DockerRuntime(Protocol):
    # -------------------------------
    # Containers
    # -------------------------------
    async def run(
        self,
        *,
        image: str,
        internal_port: int,
        host_port: int | None,
        memory_limit_mb: int,
    ) -> tuple[str, int | None]:
        """Run a container from an image. Returns (docker_id, exposed_port)."""
        ...

    async def stop(self, docker_id: str) -> None:
        """Stop a running container."""
        ...

    async def start(self, docker_id: str) -> int | None:
        """Start a stopped container. Returns exposed port."""
        ...

    async def remove(self, docker_id: str) -> None:
        """Remove a container completely."""
        ...

    async def exists(self, docker_id: str) -> bool:
        """Check if a container exists in Docker."""
        ...

    async def logs(self, container_id: str, tail: int = 100) -> str:
        """Get the logs from a container"""
        ...
    # -------------------------------
    # Images
    # -------------------------------
    async def load_image(self, path: str) -> str:
        """Load a .tar Docker image from disk. Returns Docker image ID."""
        ...

    async def remove_image(self, docker_id: str) -> None:
        """Remove a Docker image by ID."""
        ...

    async def exists_image(self, docker_id: str) -> bool:
        """Check if a Docker image exists."""
        ...

class DockerImageRepository(Protocol):
    async def get(self, image_id: UUID) -> DockerImage | None:
        pass

    async def list(self) -> List[DockerImage]:
        pass

    async def create(self, docker_image: DockerImage) -> None:
        pass
    
    async def update(self, docker_image: DockerImage) -> None:
        pass
    
    async def delete(self, image_id: UUID) -> None:
        pass

class UploadedImageRepository(Protocol):
    async def get(self, uploaded_image_id: UUID) -> UploadedImage | None:
        pass

    async def list(self) -> List[UploadedImage]:
        pass

    async def create(self, uploaded_image: UploadedImage) -> None:
        pass

    async def update(self, uploaded_image: UploadedImage) -> None:
        pass

    async def delete(self, uploaded_image_id: UUID) -> None:
        pass
