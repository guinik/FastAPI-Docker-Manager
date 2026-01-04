import asyncio
from typing import Optional, Tuple
from docker import from_env
from docker.models.images import Image
from docker.errors import NotFound, APIError

from app.domain.ports import DockerRuntime


class DockerSDKRuntime(DockerRuntime):
    def __init__(self):
        self.docker_client = from_env()

    # -------------------------------
    # Container lifecycle
    # -------------------------------
    async def run(
        self,
        *,
        image: str,
        internal_port: int,
        host_port: Optional[int] = None,
        memory_limit_mb: int,
    ) -> Tuple[str, Optional[int]]:
        """Run a container and return (docker_id, exposed_port)."""
        try:
            docker_container = await asyncio.to_thread(
                self.docker_client.containers.run,
                image,
                detach=True,
                ports={f"{internal_port}/tcp": host_port} if host_port else None,
                mem_limit=f"{max(memory_limit_mb, 6)}m",
            )
            await asyncio.to_thread(docker_container.reload)

            port_binding = docker_container.attrs["NetworkSettings"]["Ports"].get(
                f"{internal_port}/tcp"
            )
            exposed_port = int(port_binding[0]["HostPort"]) if port_binding else None
            return docker_container.id, exposed_port

        except APIError as e:
            raise RuntimeError(f"Docker run failed: {e}")

    async def stop(self, docker_id: str) -> None:
        try:
            container = await asyncio.to_thread(self.docker_client.containers.get, docker_id)
            await asyncio.to_thread(container.stop)
        except NotFound:
            pass

    async def start(self, docker_id: str) -> Optional[int]:
        try:
            container = await asyncio.to_thread(self.docker_client.containers.get, docker_id)
            await asyncio.to_thread(container.start)
            await asyncio.to_thread(container.reload)
            ports = container.attrs["NetworkSettings"]["Ports"]
            if ports:
                for binding in ports.values():
                    if binding:
                        return int(binding[0]["HostPort"])
            return None
        except NotFound:
            return None

    async def remove(self, docker_id: str) -> None:
        try:
            container = await asyncio.to_thread(self.docker_client.containers.get, docker_id)
            await asyncio.to_thread(container.remove)
        except NotFound:
            pass

    async def exists(self, docker_id: str) -> bool:
        try:
            await asyncio.to_thread(self.docker_client.containers.get, docker_id)
            return True
        except NotFound:
            return False


    async def get_status(self, docker_id: str) -> Optional[str]:
        """
        Return the container's status as a string ("running", "exited", etc.)
        Returns None if container does not exist.
        """
        try:
            container = await asyncio.to_thread(self.docker_client.containers.get, docker_id)
            await asyncio.to_thread(container.reload)
            return container.status  # "running", "exited", "paused", etc.
        except NotFound:
            return None

    async def get_exposed_port(self, docker_id: str, internal_port: int) -> Optional[int]:
        """
        Return the host port mapped to the given internal port for a container.
        Returns None if not mapped or container does not exist.
        """
        try:
            container = await asyncio.to_thread(self.docker_client.containers.get, docker_id)
            await asyncio.to_thread(container.reload)
            ports = container.attrs["NetworkSettings"]["Ports"]
            if ports and f"{internal_port}/tcp" in ports:
                binding = ports[f"{internal_port}/tcp"]
                if binding:
                    return int(binding[0]["HostPort"])
            return None
        except NotFound:
            return None

    # -------------------------------
    # Image lifecycle
    # -------------------------------
    async def load_image(self, path: str) -> str:
        """Load a .tar image and return Docker image ID."""
        try:
            with open(path, "rb") as f:
                loaded = await asyncio.to_thread(self.docker_client.images.load, f.read())
            # Return first loaded image ID
            docker_img: Image = loaded[0]
            return docker_img.id
        except Exception as e:
            raise RuntimeError(f"Failed to load Docker image: {e}")

    async def remove_image(self, docker_id: str) -> None:
        try:
            await asyncio.to_thread(self.docker_client.images.remove, docker_id, force=True)
        except NotFound:
            pass

    async def exists_image(self, docker_id: str) -> bool:
        try:
            await asyncio.to_thread(self.docker_client.images.get, docker_id)
            return True
        except NotFound:
            return False
