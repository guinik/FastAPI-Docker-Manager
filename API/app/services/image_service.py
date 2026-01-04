import shutil
from uuid import UUID, uuid4
from datetime import datetime
from typing import Dict, List, Optional

from app.domain.image import UploadedImage, DockerImage
from app.domain.ports import UploadedImageRepository, DockerImageRepository, DockerRuntime
from app.core.config import Settings


class ImageService:
    def __init__(
        self,
        uploaded_repo: UploadedImageRepository,
        docker_repo: DockerImageRepository,
        docker_runtime: DockerRuntime,
        settings: Settings | None = None,
    ):
        self.uploaded_repo = uploaded_repo
        self.docker_repo = docker_repo
        self.docker_runtime = docker_runtime
        self.settings = settings or Settings()
        self.settings.IMAGE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

        # Optional in-memory caches
        self.uploaded_images: Dict[UUID, UploadedImage] = {}
        self.docker_images: Dict[UUID, DockerImage] = {}

    # -------------------------------
    # Load everything from repositories
    # -------------------------------
    async def load_from_repos(self):
        uploaded_list = await self.uploaded_repo.list()
        docker_list = await self.docker_repo.list()

        self.uploaded_images = {img.id: img for img in uploaded_list}
        self.docker_images = {img.id: img for img in docker_list}

        print(f"[DB LOAD] {len(self.uploaded_images)} uploaded images, {len(self.docker_images)} Docker images loaded")

    # -------------------------------
    # Register a new uploaded image
    # -------------------------------
    async def register_upload(self, file) -> UploadedImage:
        file.file.seek(0, 2)
        size_mb = file.file.tell() / (1024 * 1024)
        if size_mb > self.settings.MAX_IMAGE_SIZE_MB:
            raise ValueError(f"File too large ({size_mb:.2f} MB)")
        file.file.seek(0)

        image_id = uuid4()
        image_path = self.settings.IMAGE_STORAGE_DIR / f"{image_id}_{file.filename}"

        with open(image_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        uploaded = UploadedImage(
            id=image_id,
            filename=file.filename,
            path=str(image_path),
            status="pending",
            created_at=datetime.utcnow(),
        )

        await self.uploaded_repo.create(uploaded)
        self.uploaded_images[uploaded.id] = uploaded
        return uploaded

    # -------------------------------
    # Load uploaded image into Docker
    # -------------------------------
    async def load_image(self, uploaded_image_id: UUID) -> DockerImage:
        uploaded = await self.uploaded_repo.get(uploaded_image_id)
        if not uploaded:
            raise ValueError("Uploaded image not found")

        # Load into Docker
        docker_id = await self.docker_runtime.load_image(uploaded.path)

        # Create DockerImage record
        docker_img = DockerImage(
            id=uuid4(),
            name=uploaded.filename,
            tag="latest",
            docker_id=docker_id,
            status="loaded",
            uploaded_image_id=uploaded.id,
        )

        # Save in repository
        await self.docker_repo.create(docker_img)

        # Update uploaded image status
        uploaded.status = "loaded"
        await self.uploaded_repo.update(uploaded)

        # Update in-memory caches
        self.uploaded_images[uploaded.id] = uploaded
        self.docker_images[docker_img.id] = docker_img

        return docker_img

    # -------------------------------
    # List / Get Uploaded Images
    # -------------------------------
    async def list_uploaded_images(self, latest_only: bool = False) -> List[UploadedImage]:
        images = await self.uploaded_repo.list()
        if latest_only:
            latest_map: Dict[str, UploadedImage] = {}
            for img in images:
                current = latest_map.get(img.filename)
                if not current or img.created_at > current.created_at:
                    latest_map[img.filename] = img
            return list(latest_map.values())
        return images

    async def get_uploaded_image(self, image_id: UUID) -> UploadedImage:
        uploaded = await self.uploaded_repo.get(image_id)
        if not uploaded:
            raise ValueError("Uploaded image not found")
        return uploaded

    async def get_uploaded_image_by_name(self, filename: str, latest: bool = True) -> Optional[UploadedImage]:
        images = [img for img in await self.uploaded_repo.list() if img.filename == filename]
        if not images:
            return None
        if latest:
            return max(images, key=lambda x: x.created_at)
        return images[0]

    # -------------------------------
    # List / Get Docker Images
    # -------------------------------
    async def list_docker_images(self) -> List[DockerImage]:
        return await self.docker_repo.list()

    async def get_docker_image(self, image_id: UUID) -> DockerImage:
        docker_img = await self.docker_repo.get(image_id)
        if not docker_img:
            raise ValueError("Docker image not found")
        return docker_img
