import asyncio
from uuid import uuid4, UUID
from datetime import datetime
from typing import Dict
from dataclasses import dataclass, field
import docker
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


class ContainerService:
    def __init__(self):
        self._containers: Dict[UUID, Container] = {}
        self._lock = asyncio.Lock()
        self._next_port = 8002
        self.docker_client = docker.from_env()

    async def create_container(self, image, cpu, memory) -> Container:
        container_id = uuid4()
        container = Container(
            id=container_id,
            image=image,
            status="pending",
            cpu_limit=cpu,
            memory_limit_mb=memory,
        )
        async with self._lock:
            self._containers[container_id] = container
        return container

    
    async def deploy_container(self, container_id: UUID):
        async with self._lock:
            container = self._containers[container_id]

        try:
            docker_container = await asyncio.to_thread(
                self.docker_client.containers.run,
                container.image,
                detach=True,
                ports={f"{container.internal_port}/tcp": None},
                mem_limit=f"{max(container.memory_limit_mb, 6)}m",
            )

            docker_container.reload()

            port_info = docker_container.attrs["NetworkSettings"]["Ports"][f"{container.internal_port}/tcp"]
            host_port = int(port_info[0]["HostPort"])

            async with self._lock:
                container.status = "running"
                container.exposed_port = host_port
                container.docker_id = docker_container.id

        except Exception as e:
            async with self._lock:
                container.status = "failed"
            print(f"Failed to deploy container {container_id}: {e}")




    async def list_containers(self):
        async with self._lock:
            return list(self._containers.values())
