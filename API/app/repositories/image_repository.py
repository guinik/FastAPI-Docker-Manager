# app/repositories/docker_image_repository.py
from uuid import UUID
from sqlalchemy import select, insert, update
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
                status=docker_image.status,
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
            status=row["status"],
            created_at=row["created_at"]
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
                status=r["status"],
                created_at=r["created_at"]
            )
            for r in rows
        ]

    async def update(self, docker_image: DockerImage) -> None:
        await database.execute(
            update(DockerImageDB)
            .where(DockerImageDB.id == str(docker_image.id))
            .values(
                name=docker_image.name,
                tag=docker_image.tag,
                docker_id=docker_image.docker_id,
                status=docker_image.status
            )
        )
