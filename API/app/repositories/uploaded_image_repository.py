# app/repositories/uploaded_image_repository.py
from uuid import UUID
from sqlalchemy import select, insert, update
from app.core.database import database
from app.models.db import UploadedImageDB
from app.domain.image import UploadedImage
from app.domain.ports import UploadedImageRepository


class SQLUploadedImageRepository(UploadedImageRepository):
    async def create(self, uploaded_image: UploadedImage) -> None:
        await database.execute(
            insert(UploadedImageDB).values(
                id=str(uploaded_image.id),
                filename=uploaded_image.filename,
                path=uploaded_image.path,
                status=uploaded_image.status,
                created_at=uploaded_image.created_at,
            )
        )

    async def get(self, uploaded_image_id: UUID) -> UploadedImage | None:
        row = await database.fetch_one(
            select(UploadedImageDB).where(UploadedImageDB.id == str(uploaded_image_id))
        )
        if not row:
            return None
        return UploadedImage(
            id=UUID(row["id"]),
            filename=row["filename"],
            path=row["path"],
            status=row["status"],
            created_at=row["created_at"],
        )

    async def list(self) -> list[UploadedImage]:
        rows = await database.fetch_all(select(UploadedImageDB))
        return [
            UploadedImage(
                id=UUID(r["id"]),
                filename=r["filename"],
                path=r["path"],
                status=r["status"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    async def update(self, uploaded_image: UploadedImage) -> None:
        await database.execute(
            update(UploadedImageDB)
            .where(UploadedImageDB.id == str(uploaded_image.id))
            .values(
                filename=uploaded_image.filename,
                path=uploaded_image.path,
                status=uploaded_image.status,
                created_at=uploaded_image.created_at,
            )
        )
