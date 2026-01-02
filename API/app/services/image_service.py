# app/services/image_service.py
import shutil
import asyncio
import docker
from uuid import UUID, uuid4
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select, insert, update

from app.models.image import UploadedImage, DockerImage
from app.core.database import database 
from app.models.db import UploadedImageDB, DockerImageDB 
from app.core.config import Settings


class ImageService:
    def __init__(self):
        self.docker_client = docker.from_env()
        self.settings = Settings()
        self.settings.IMAGE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

        # In-memory caches (optional, for speed)
        self.uploaded_images: Dict[UUID, UploadedImage] = {}
        self.docker_images: Dict[UUID, DockerImage] = {}

    # -------------------------------
    # Load everything from the DB on startup
    # -------------------------------
    async def load_from_db(self):
        # Uploaded images
        rows = await database.fetch_all(select(UploadedImageDB))
        for row in rows:
            img = UploadedImage(
                id=UUID(row["id"]),
                filename=row["filename"],
                path=row["path"],
                status=row["status"],
                created_at=row["created_at"],
            )
            self.uploaded_images[img.id] = img

        # Docker images
        rows = await database.fetch_all(select(DockerImageDB))
        for row in rows:
            docker_img = DockerImage(
                id=UUID(row["id"]),
                name=row["name"],
                tag=row["tag"],
                docker_id=row["docker_id"],
                status=row["status"],
                uploaded_image_id=UUID(row["uploaded_image_id"])
            )
            self.docker_images[docker_img.id] = docker_img

        print(f"[DB LOAD] {len(self.uploaded_images)} uploaded images, {len(self.docker_images)} Docker images loaded")

    # -------------------------------
    # Upload a new image
    # -------------------------------
    async def register_upload(self, file) -> UploadedImage:
        file.file.seek(0, 2)
        size_mb = file.file.tell() / (1024 * 1024)
        if size_mb > self.settings.MAX_IMAGE_SIZE_MB:
            raise ValueError(f"File too large ({size_mb:.2f} MB)")
        file.file.seek(0)

        image_id = str(uuid4())
        image_path = self.settings.IMAGE_STORAGE_DIR / f"{image_id}_{file.filename}"

        with open(image_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Insert into DB
        query = insert(UploadedImageDB).values(
            id=image_id,
            filename=file.filename,
            path=str(image_path),
            status="pending",
            created_at=datetime.utcnow()
        )
        await database.execute(query)

        uploaded = UploadedImage(
            id=UUID(image_id),
            filename=file.filename,
            path=str(image_path),
            status="pending",
            created_at=datetime.utcnow()
        )
        self.uploaded_images[uploaded.id] = uploaded
        return uploaded

    # -------------------------------
    # Load uploaded image into Docker
    # -------------------------------
    async def load_image(self, uploaded_image_id: UUID) -> DockerImage:
        uploaded_image_id = str(uploaded_image_id)
        row = await database.fetch_one(select(UploadedImageDB).where(UploadedImageDB.id == uploaded_image_id))
        if not row:
            raise ValueError("Uploaded image not found")

        try:
            with open(row["path"], "rb") as f:
                loaded_images = await asyncio.to_thread(self.docker_client.images.load, f.read())

            docker_obj = loaded_images[0]
            name, tag = docker_obj.tags[0].split(":") if docker_obj.tags else (row["filename"], "latest")

            # Upsert DockerImage in DB
            existing = await database.fetch_one(
                select(DockerImageDB).where(DockerImageDB.uploaded_image_id == uploaded_image_id)
            )

            if existing:
                query = (
                    update(DockerImageDB)
                    .where(DockerImageDB.uploaded_image_id == uploaded_image_id)
                    .values(name=name, tag=tag, docker_id=docker_obj.id, status="loaded")
                )
                await database.execute(query)
                docker_id = existing["id"]
            else:
                docker_id = str(uuid4())
                query = insert(DockerImageDB).values(
                    id=docker_id,
                    uploaded_image_id=uploaded_image_id,
                    name=name,
                    tag=tag,
                    docker_id=docker_obj.id,
                    status="loaded"
                )
                await database.execute(query)

            # Update uploaded image status
            await database.execute(
                update(UploadedImageDB).where(UploadedImageDB.id == uploaded_image_id).values(status="loaded")
            )

            docker_img = DockerImage(
                id=UUID(docker_id),
                name=name,
                tag=tag,
                docker_id=docker_obj.id,
                status="loaded",
                uploaded_image_id=UUID(uploaded_image_id)
            )
            self.docker_images[docker_img.id] = docker_img
            return docker_img

        except Exception as e:
            await database.execute(
                update(UploadedImageDB).where(UploadedImageDB.id == uploaded_image_id).values(status="failed")
            )
            raise e

    # -------------------------------
    # List uploaded images
    # -------------------------------
    async def list_uploaded_images(self, latest_only: bool = False) -> List[UploadedImage]:
        rows = await database.fetch_all(select(UploadedImageDB))
        images = [
            UploadedImage(
                id=UUID(r["id"]),
                filename=r["filename"],
                path=r["path"],
                status=r["status"],
                created_at=r["created_at"]
            )
            for r in rows
        ]

        if latest_only:
            latest_map: Dict[str, UploadedImage] = {}
            for img in images:
                current = latest_map.get(img.filename)
                if not current or img.created_at > current.created_at:
                    latest_map[img.filename] = img
            return list(latest_map.values())

        return images

    # -------------------------------
    # List Docker images
    # -------------------------------
    async def list_docker_images(self) -> List[DockerImage]:
        rows = await database.fetch_all(select(DockerImageDB))
        return [
            DockerImage(
                id=UUID(r["id"]),
                name=r["name"],
                tag=r["tag"],
                docker_id=r["docker_id"],
                status=r["status"],
                uploaded_image_id=UUID(r["uploaded_image_id"])
            )
            for r in rows
        ]

    # -------------------------------
    # Get single uploaded image
    # -------------------------------
    async def get_uploaded_image(self, image_id: UUID) -> UploadedImage:
        
        image_id = str(image_id)
        
        row = await database.fetch_one(select(UploadedImageDB).where(UploadedImageDB.id == image_id))
        if not row:
            raise ValueError("Uploaded image not found")
        return UploadedImage(
            id=UUID(row["id"]),
            filename=row["filename"],
            path=row["path"],
            status=row["status"],
            created_at=row["created_at"]
        )

    # -------------------------------
    # Get latest uploaded image by name
    # -------------------------------
    async def get_uploaded_image_by_name(self, filename: str, latest: bool = True) -> Optional[UploadedImage]:
        rows = await database.fetch_all(select(UploadedImageDB).where(UploadedImageDB.filename == filename))
        if not rows:
            return None

        images = [
            UploadedImage(
                id=UUID(r["id"]),
                filename=r["filename"],
                path=r["path"],
                status=r["status"],
                created_at=row["created_at"]
            )
            for r in rows
        ]

        if latest:
            return max(images, key=lambda x: x.created_at)
        return images[0]

    # -------------------------------
    # Get single Docker image
    # -------------------------------
    async def get_docker_image(self, image_id: UUID) -> DockerImage:
        image_id = str(image_id)
        row = await database.fetch_one(select(DockerImageDB).where(DockerImageDB.id == image_id))
        if not row:
            raise ValueError("Docker image not found")
        return DockerImage(
            id=UUID(row["id"]),
            name=row["name"],
            tag=row["tag"],
            docker_id=row["docker_id"],
            status=row["status"],
            uploaded_image_id=UUID(row["uploaded_image_id"])
        )
