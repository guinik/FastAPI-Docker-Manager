# app/repositories/docker_image_repository.py
from uuid import UUID
from sqlalchemy import select, insert, update, delete
from app.core.database import database
from app.models.db import DockerImageDB
from app.domain.image import DockerImage
from app.domain.ports import DockerImageRepository


class SQLDockerImageRepository(DockerImageRepository):
    async def create(self, docker_image: DockerImage) -> None:
        await database.execute(
            insert(DockerImageDB).values(
                id=str(docker_image.id),
                uploaded_image_id=str(docker_image.uploaded_image_id),
                name=docker_image.name,
                tag=docker_image.tag,
                docker_id=docker_image.docker_id,
                created_at=docker_image.created_at,
                is_active=docker_image.is_active
            )
        )

    async def get(self, image_id: UUID) -> DockerImage | None:
        row = await database.fetch_one(
            select(DockerImageDB).where(DockerImageDB.id == str(image_id))
        )
        if not row:
            return None

        return DockerImage(
            id=UUID(row["id"]),
            uploaded_image_id=UUID(row["uploaded_image_id"]),
            name=row["name"],
            tag=row["tag"],
            docker_id=row["docker_id"],
            created_at=row["created_at"],
            is_active=row["is_active"]
        )

    async def list(self) -> list[DockerImage]:
        rows = await database.fetch_all(select(DockerImageDB))
        return [
            DockerImage(
                id=UUID(r["id"]),
                uploaded_image_id=UUID(r["uploaded_image_id"]),
                name=r["name"],
                tag=r["tag"],
                docker_id=r["docker_id"],
                created_at=r["created_at"],
                is_active=r["is_active"]
            )
            for r in rows
        ]

    async def update(self, docker_image: DockerImage) -> None:
        """
        Update a DockerImage in the DB. Can be used to set `is_active` True/False or
        update other fields like docker_id.
        """
        await database.execute(
            update(DockerImageDB)
            .where(DockerImageDB.id == str(docker_image.id))
            .values(
                docker_id=docker_image.docker_id,
                uploaded_image_id=str(docker_image.uploaded_image_id),
                created_at=docker_image.created_at,
                is_active=docker_image.is_active,  # <-- update active state
            )
        )

    async def delete(self, image_id: UUID) -> None:
        """
        Delete a DockerImage from the DB by its UUID.
        """
        query = delete(DockerImageDB).where(DockerImageDB.id == str(image_id))
        await database.execute(query)
