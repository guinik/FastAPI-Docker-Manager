# app/services/container_service.py
import asyncio
from uuid import UUID, uuid4
from typing import List, Optional

import docker
from sqlalchemy import select, insert, update
from fastapi import HTTPException

from app.models.container import Container
from app.models.db import ContainerDB, DockerImageDB
from app.core.database import database


class ContainerService:
    def __init__(self):
        self.docker_client = docker.from_env()
        self._lock = asyncio.Lock()  # For async safety

    # -------------------------------
    # CRUD
    # -------------------------------
    async def create_container(
        self,
        image: str,
        cpu_limit: float = 0.5,
        memory_limit_mb: int = 128,
        internal_port: int = 80,
    ) -> Container:
        """
        Create a pending container DB record with a given image name.
        """
        container_id = str(uuid4())

        # Insert into DB
        query = insert(ContainerDB).values(
            id=container_id,
            docker_image_id=None,  # not linked to DockerImageDB, just a string image
            image=image,
            status="pending",
            cpu_limit=cpu_limit,
            memory_limit_mb=memory_limit_mb,
            internal_port=internal_port,
        )
        await database.execute(query)

        return Container(
            id=UUID(container_id),
            image=image,
            status="pending",
            cpu_limit=cpu_limit,
            memory_limit_mb=memory_limit_mb,
            internal_port=internal_port,
        )

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
    async def deploy_container(self, container_id: UUID, host_port: Optional[int] = None) -> Container:
        container = await self.get_container(container_id)

        if container.status == "running":
            return container  # Already running

        try:
            docker_container = await asyncio.to_thread(
                self.docker_client.containers.run,
                container.image,
                detach=True,
                ports={f"{container.internal_port}/tcp": host_port} if host_port else {f"{container.internal_port}/tcp": None},
                mem_limit=f"{max(container.memory_limit_mb, 6)}m",
            )

            await asyncio.to_thread(docker_container.reload)

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
            print(f"[DEPLOY ERROR] {container_id}: {exc}")

        return container
    
    
    async def run_from_image(
        self,
        docker_image_id: UUID,
        cpu_limit: float = 0.5,
        memory_limit_mb: int = 128,
        internal_port: int = 80,
        host_port: int | None = None,
    ) -> Container:
        """
        Create a container from a loaded DockerImage (by UUID) and run it.
        """
        docker_row = await database.fetch_one(
            select(DockerImageDB).where(DockerImageDB.id == str(docker_image_id))
        )
        if not docker_row:
            raise HTTPException(404, f"Docker image {docker_image_id} not found")

        image_full_name = f"{docker_row['name']}:{docker_row['tag']}"

        container_id = str(uuid4())
        await database.execute(
            insert(ContainerDB).values(
                id=container_id,
                docker_image_id=str(docker_image_id),
                image=image_full_name,
                status="pending",
                cpu_limit=cpu_limit,
                memory_limit_mb=memory_limit_mb,
                internal_port=internal_port,
            )
        )

        container = Container(
            id=UUID(container_id),
            docker_image_id=docker_image_id,
            image=image_full_name,
            status="pending",
            cpu_limit=cpu_limit,
            memory_limit_mb=memory_limit_mb,
            internal_port=internal_port,
        )

        try:
            docker_container = await asyncio.to_thread(
                self.docker_client.containers.run,
                image_full_name,
                detach=True,
                ports={f"{internal_port}/tcp": host_port} if host_port else {f"{internal_port}/tcp": None},
                mem_limit=f"{max(memory_limit_mb, 6)}m",
            )

            await asyncio.to_thread(docker_container.reload)

            port_binding = docker_container.attrs["NetworkSettings"]["Ports"].get(
                f"{internal_port}/tcp"
            )
            exposed_port = int(port_binding[0]["HostPort"]) if port_binding else None

            await database.execute(
                update(ContainerDB)
                .where(ContainerDB.id == container_id)
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
            # mark failed in DB
            await database.execute(
                update(ContainerDB)
                .where(ContainerDB.id == container_id)
                .values(status="failed")
            )
            container.status = "failed"
            print(f"[RUN ERROR] Failed to run {image_full_name}: {exc}")

        return container

