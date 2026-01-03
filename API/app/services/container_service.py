# app/services/container_service.py
import asyncio
from uuid import UUID, uuid4
from typing import List
from sqlalchemy import select, insert, update
from fastapi import HTTPException

from app.models.container import Container
from app.models.db import ContainerDB, DockerImageDB
from app.core.database import database
import docker
from docker.errors import NotFound

class ContainerService:
    def __init__(self):
        self.docker_client = docker.from_env()
        self._lock = asyncio.Lock()
        self._reconcile_task: asyncio.Task | None = None


    # -------------------------------
    # CRUD
    # -------------------------------
    async def create_container(
        self,
        *,
        image: str | None,
        image_id: UUID | None,
        cpu_limit: float,
        memory_limit_mb: int,
        internal_port: int,
        host_port: int | None,
        auto_start: bool,
    ) -> Container:
        """
        Create a container from either a raw image string or an uploaded image UUID.
        """
        if image_id:
            docker_row = await database.fetch_one(
                select(DockerImageDB).where(DockerImageDB.id == str(image_id))
            )
            if not docker_row:
                raise HTTPException(404, "Docker image not found")

            image_ref = f"{docker_row['name']}:{docker_row['tag']}"
        else:
            image_ref = image  # raw string

        container_id = str(uuid4())

        await database.execute(
            insert(ContainerDB).values(
                id=container_id,
                docker_image_id=str(image_id) if image_id else None,
                image=image_ref,
                status="pending",
                cpu_limit=cpu_limit,
                memory_limit_mb=memory_limit_mb,
                internal_port=internal_port,
            )
        )

        container = Container(
            id=UUID(container_id),
            docker_image_id=image_id,
            image=image_ref,
            status="pending",
            cpu_limit=cpu_limit,
            memory_limit_mb=memory_limit_mb,
            internal_port=internal_port,
        )

        if auto_start:
            await self._run_new_container(container, host_port)

        return container

    async def list_containers(self) -> List[Container]:
        rows = await database.fetch_all(select(ContainerDB))
        return [
            Container(
                id=UUID(r["id"]),
                docker_image_id=UUID(r["docker_image_id"]) if r["docker_image_id"] else None,
                image=r["image"],
                status=r["status"],
                cpu_limit=r["cpu_limit"],
                memory_limit_mb=r["memory_limit_mb"],
                internal_port=r["internal_port"],
                exposed_port=r["exposed_port"],
                docker_id=r["docker_id"],
            )
            for r in rows
        ]

    async def get_container(self, container_id: UUID) -> Container:
        row = await database.fetch_one(
            select(ContainerDB).where(ContainerDB.id == str(container_id))
        )
        if not row:
            raise HTTPException(404, "Container not found")
        return Container(
            id=UUID(row["id"]),
            docker_image_id=UUID(row["docker_image_id"]) if row["docker_image_id"] else None,
            image=row["image"],
            status=row["status"],
            cpu_limit=row["cpu_limit"],
            memory_limit_mb=row["memory_limit_mb"],
            internal_port=row["internal_port"],
            exposed_port=row["exposed_port"],
            docker_id=row["docker_id"],
        )

    async def delete_container(self, container_id: UUID) -> None:
        container = await self.get_container(container_id)
        if container.status == "running":
            raise HTTPException(409, "Container is running. Stop it before deleting.")

        # Remove from Docker if exists
        if container.docker_id:
            try:
                await asyncio.to_thread(
                    self.docker_client.containers.get(container.docker_id).remove
                )
            except Exception:
                pass  # ignore Docker removal errors

        # Delete from DB
        await database.execute(
            ContainerDB.__table__.delete().where(ContainerDB.id == str(container_id))
        )

    # -------------------------------
    # Docker lifecycle
    # -------------------------------
    async def _run_new_container(
        self,
        container: Container,
        host_port: int | None,
    ):
        try:
            docker_container = await asyncio.to_thread(
                self.docker_client.containers.run,
                container.image,
                detach=True,
                ports={f"{container.internal_port}/tcp": host_port}
                if host_port
                else {f"{container.internal_port}/tcp": None},
                mem_limit=f"{max(container.memory_limit_mb, 6)}m",
            )
                    

            await asyncio.to_thread(docker_container.reload)

            port_binding = docker_container.attrs["NetworkSettings"]["Ports"].get(
                f"{container.internal_port}/tcp"
            )
            print("Docker container created:", docker_container.id)
            exposed_port = int(port_binding[0]["HostPort"]) if port_binding else None
            await database.execute(
                update(ContainerDB)
                .where(ContainerDB.id == str(container.id))
                .values(
                    status="running",
                    docker_id=docker_container.id,
                    exposed_port=exposed_port,
                )
            )

            container.status = "running"
            container.docker_id = docker_container.id
            container.exposed_port = exposed_port

        except Exception as exc:
            await database.execute(
                update(ContainerDB)
                .where(ContainerDB.id == str(container.id))
                .values(status="failed")
            )
            container.status = "failed"
            print(f"[RUN ERROR] {container.id}: {exc}")


    async def start_container(
        self,
        container_id: UUID
    ) -> Container:
        """
        Start a container that already exists in Docker.
        Fails if the container has no Docker runtime (docker_id is None).
        """
        container = await self.get_container(container_id)

        if container.status == "running":
            return container
        print(container)
        if not container.docker_id:
            raise HTTPException(
                409, "Cannot start container: it has no existing Docker Container instance."
            )
        
        await self._start_existing_container(container)
        return container


    async def stop_container(self, container_id: UUID) -> Container:
        container = await self.get_container(container_id)

        if container.status != "running":
            return container  # idempotent: nothing to do

        if not container.docker_id:
            raise HTTPException(409, "Container has no Docker runtime")

        try:
            docker_container = await asyncio.to_thread(
                self.docker_client.containers.get,
                container.docker_id,
            )

            await asyncio.to_thread(docker_container.stop)

            await database.execute(
                update(ContainerDB)
                .where(ContainerDB.id == str(container.id))
                .values(status="stopped")
            )

            container.status = "stopped"

        except docker.errors.NotFound:
            await database.execute(
                update(ContainerDB)
                .where(ContainerDB.id == str(container.id))
                .values(status="stopped", docker_id=None)
            )
            container.status = "stopped"
            container.docker_id = None

        except Exception as exc:
            raise HTTPException(500, f"Failed to stop container: {exc}")

        return container
    

    # --------------------------------------------------------
    #
    #       RECONCILITATION MECHANISM
    #
    # --------------------------------------------------------
    def start_reconciliation_loop(self, interval: float = 10.0):
        """
        Start background reconciliation loop that ensures DB matches Docker state.
        """
        if self._reconcile_task is None or self._reconcile_task.done():
            self._reconcile_task = asyncio.create_task(self._reconcile_loop(interval))

    # -------------------------------
    # Reconciliation method
    # -------------------------------
    async def reconcile_running_containers(self):
        rows = await database.fetch_all(
            select(ContainerDB).where(ContainerDB.status == "running")
        )

        for r in rows:
            container_id = r["id"]
            docker_id = r["docker_id"]

            if not docker_id:
                await database.execute(
                    update(ContainerDB)
                    .where(ContainerDB.id == container_id)
                    .values(status="failed")
                )
                continue

            try:
                container = await asyncio.to_thread(
                    self.docker_client.containers.get, docker_id
                )
                if container.status != "running":
                    await database.execute(
                        update(ContainerDB)
                        .where(ContainerDB.id == container_id)
                        .values(status="stopped", exposed_port = None)
                    )
                    print(f"[RECONCILE] Container {container_id} exists but stopped")

            except docker.errors.NotFound:
                await database.execute(
                    update(ContainerDB)
                    .where(ContainerDB.id == container_id)
                    .values(status="failed", docker_id=None)
                )
                print(f"[RECONCILE] Container {container_id} no longer exists, docker_id cleared")

        #-----------------------------------------------------------------------------
        #
        #  Internal methods
        #
        #-----------------------------------------------------------------------------
    async def _start_existing_container(
        self,
        container: Container
        ):
        """
        Resume an existing Docker container. Only called if container.docker_id exists.
        """
        try:
            docker_container = await asyncio.to_thread(
                self.docker_client.containers.get,
                container.docker_id
            )

            await asyncio.to_thread(docker_container.start)
            await asyncio.to_thread(docker_container.reload)

            # Update exposed port (if port mapping exists)
            port_binding = docker_container.attrs["NetworkSettings"]["Ports"].get(
                f"{container.internal_port}/tcp"
            )
            exposed_port = int(port_binding[0]["HostPort"]) if port_binding else None

            # Update DB
            await database.execute(
                update(ContainerDB)
                .where(ContainerDB.id == str(container.id))
                .values(
                    status="running",
                    exposed_port=exposed_port,
                )
            )

            # Update in-memory container
            container.status = "running"
            container.exposed_port = exposed_port

        except NotFound:
            raise HTTPException(
                404, "Docker container not found. It may have been removed."
            )

        except Exception as exc:
            raise HTTPException(500, f"Failed to start container: {exc}")
            

    async def _reconcile_loop(self, interval: float):
        """
            Internal loop for reconcilation, interval is the time of sleeping between reconciliations. 
            To be thought if this design is the best, or do it per queried.
        
        """
        while True:
            try:
                await self.reconcile_running_containers()
            except Exception as e:
                print(f"[RECONCILE ERROR] {e}")
            await asyncio.sleep(interval)
