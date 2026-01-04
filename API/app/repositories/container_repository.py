from uuid import UUID
from sqlalchemy import select, insert, update, delete

from app.core.database import database
from app.models.db import ContainerDB
from app.domain.container import Container
from app.domain.ports import ContainerRepository


class SQLContainerRepository(ContainerRepository):
    async def create(self, container: Container) -> None:
        await database.execute(
            insert(ContainerDB).values(
                id=str(container.id),
                docker_image_id=str(container.docker_image_id)
                if container.docker_image_id
                else None,
                image=container.image,
                status=container.status,
                cpu_limit=container.cpu_limit,
                memory_limit_mb=container.memory_limit_mb,
                internal_port=container.internal_port,
                exposed_port=container.exposed_port,
                docker_id=container.docker_id,
            )
        )

    async def get(self, container_id: UUID) -> Container | None:
        row = await database.fetch_one(
            select(ContainerDB).where(ContainerDB.id == str(container_id))
        )

        if not row:
            return None

        return Container(
            id=UUID(row["id"]),
            docker_image_id=UUID(row["docker_image_id"])
            if row["docker_image_id"]
            else None,
            image=row["image"],
            status=row["status"],
            cpu_limit=row["cpu_limit"],
            memory_limit_mb=row["memory_limit_mb"],
            internal_port=row["internal_port"],
            exposed_port=row["exposed_port"],
            docker_id=row["docker_id"],
        )

    async def list(self) -> list[Container]:
        rows = await database.fetch_all(select(ContainerDB))

        return [
            Container(
                id=UUID(r["id"]),
                docker_image_id=UUID(r["docker_image_id"])
                if r["docker_image_id"]
                else None,
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

    async def update(
        self,
        container_id: UUID,
        *,
        status: str | None = None,
        docker_id: str | None = None,
        exposed_port: int | None = None,
    ) -> None:
        values = {}

        if status is not None:
            values["status"] = status
        if docker_id is not None:
            values["docker_id"] = docker_id
        if exposed_port is not None:
            values["exposed_port"] = exposed_port

        if not values:
            return

        await database.execute(
            update(ContainerDB)
            .where(ContainerDB.id == str(container_id))
            .values(**values)
        )

    async def delete(self, container_id: UUID) -> None:
        await database.execute(
            delete(ContainerDB).where(ContainerDB.id == str(container_id))
        )
