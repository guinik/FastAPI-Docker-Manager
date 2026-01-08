# app/services/container_service.py
import asyncio
from uuid import UUID, uuid4
from typing import List
from fastapi import HTTPException
from datetime import datetime, timezone
from app.domain.container import Container
from app.domain.ports import ContainerRepository, DockerImageRepository, DockerRuntime


class ContainerService:
    def __init__(
        self,
        container_repository: ContainerRepository,
        docker_image_repo: DockerImageRepository,
        docker_runtime: DockerRuntime,
    ):
        self.container_repository = container_repository
        self.docker_image_repo = docker_image_repo
        self.docker_runtime = docker_runtime
        self._lock = asyncio.Lock()
        self._reconcile_task: asyncio.Task | None = None

    # -------------------------------
    # CRUD
    # -------------------------------
    async def create_container(
        self,
        *,
        image: str | None = None,
        image_id: UUID | None = None,
        cpu_limit: float = 0.1,
        memory_limit_mb: int = 128,
        internal_port: int = 80,
        host_port: int | None = None
    ) -> Container:
        """
        Create a container from either a raw image string or an uploaded image UUID.
        """
        if image_id:
            image_container = await self.docker_image_repo.get(image_id)
            if not image_container:
                raise HTTPException(404, "Docker image not found")
            image_ref = image_container.docker_id

            if image_container.is_active == False:
                raise HTTPException(status_code=409, detail="Docker image is not active")
        else:
            image_ref = image  # raw image string

        container_id = uuid4()
        container = Container(
            id=container_id,
            docker_image_id=image_id,
            image=image_ref,
            status="pending",
            cpu_limit=cpu_limit,
            memory_limit_mb=memory_limit_mb,
            internal_port=internal_port,
            created_at = datetime.now(timezone.utc)
        )

        await self.container_repository.create(container)

        await self._run_new_container(container, host_port)

        return container

    async def list_containers(self) -> List[Container]:
        return await self.container_repository.list()

    async def get_container(self, container_id: UUID) -> Container:
        container = await self.container_repository.get(container_id)
        if not container:
            raise HTTPException(404, "Container not found")
        return container

    async def delete_container(self, container_id: UUID) -> None:
        container = await self.get_container(container_id)
        if container.status == "running":
            raise HTTPException(409, "Container is running. Stop it before deleting.")

        if container.docker_id:
            await self.docker_runtime.remove(container.docker_id)

        await self.container_repository.delete(container_id)

    async def get_container_logs(self, container_id: UUID, tail: int = 100) -> str:
        """
        Fetch logs from a running or stopped container.
        :param container_id: UUID of the container
        :param tail: number of last lines to fetch
        :return: logs as a string
        """
        container = await self.get_container(container_id)

        if not container.docker_id:
            raise HTTPException(409, "Container has no Docker runtime ID")

        try:
            logs = await self.docker_runtime.logs(container.docker_id, tail=tail)
            return logs
        except Exception as exc:
            raise HTTPException(500, f"Failed to fetch logs: {exc}")

    # -------------------------------
    # Docker lifecycle
    # -------------------------------
    async def _run_new_container(self, container: Container, host_port: int | None):
        try:
            docker_id, exposed_port = await self.docker_runtime.run(
                image=container.image,
                internal_port=container.internal_port,
                host_port=host_port,
                memory_limit_mb=container.memory_limit_mb,
            )

            container.docker_id = docker_id
            container.exposed_port = exposed_port
            container.status = "running"

            await self.container_repository.update(
                container.id,
                status="running",
                docker_id=docker_id,
                exposed_port=exposed_port,
            )

        except Exception as exc:
            container.status = "failed"
            await self.container_repository.update(container.id, status="failed")
            print(f"[RUN ERROR] {container.id}: {exc}")

    async def start_container(self, container_id: UUID) -> Container:
        container = await self.get_container(container_id)
        if container.status == "running":
            return container
        if not container.docker_id:
            raise HTTPException(409, "Cannot start container: no Docker runtime")

        exposed_port = await self.docker_runtime.start(container.docker_id)
        container.status = "running"
        container.exposed_port = exposed_port

        await self.container_repository.update(
            container.id, status="running", exposed_port=exposed_port
        )
        return container

    async def stop_container(self, container_id: UUID) -> Container:
        container = await self.get_container(container_id)
        if container.status != "running":
            return container

        if not container.docker_id:
            raise HTTPException(409, "Container has no Docker runtime")

        await self.docker_runtime.stop(container.docker_id)
        container.status = "stopped"
        await self.container_repository.update(container.id, status="stopped")
        return container

    # -------------------------------
    # Reconciliation
    # -------------------------------
    async def reconcile_running_containers(self):
        containers = await self.container_repository.list()
        for container in containers:
            if container.status != "running" or not container.docker_id:
                continue

            try:
                # Fetch Docker container info
                docker_status = await self.docker_runtime.get_status(container.docker_id)

                if docker_status is None:
                    # Container disappeared
                    container.status = "failed"
                    container.docker_id = None
                    container.exposed_port = None
                    await self.container_repository.update(
                        container.id, status="failed", docker_id=None, exposed_port=None
                    )
                    print(f"[RECONCILE] Container {container.id} no longer exists")

                elif docker_status != "running":
                    # Container exists but not running
                    container.status = "stopped"
                    container.exposed_port = None
                    await self.container_repository.update(
                        container.id, status="stopped", exposed_port=None
                    )
                    print(f"[RECONCILE] Container {container.id} exists but stopped")

                else:
                    # Still running, optionally refresh exposed port
                    exposed_port = await self.docker_runtime.get_exposed_port(container.docker_id, container.internal_port)
                    container.exposed_port = exposed_port
                    await self.container_repository.update(
                        container.id, exposed_port=exposed_port
                    )

            except Exception as e:
                print(f"[RECONCILE ERROR] Container {container.id}: {e}")


    def start_reconciliation_loop(self, interval: float = 10.0):
        if not hasattr(self, "_reconcile_task") or self._reconcile_task is None or self._reconcile_task.done():
            self._reconcile_task = asyncio.create_task(self._reconcile_loop(interval))

    async def _reconcile_loop(self, interval: float):
        while True:
            try:
                await self.reconcile_running_containers()
            except Exception as e:
                print(f"[RECONCILE ERROR] {e}")
            await asyncio.sleep(interval)
