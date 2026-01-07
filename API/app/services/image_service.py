from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Dict, List, Optional, DefaultDict
from pathlib import Path
from app.domain.image import UploadedImage, DockerImage
from app.domain.ports import UploadedImageRepository, DockerImageRepository, DockerRuntime
from app.core.config import Settings
import asyncio
import aiofiles


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
        self._locks: Dict[str, asyncio.Lock] = DefaultDict(asyncio.Lock)

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

        # Set initial status to pending
        uploaded = UploadedImage(
            id=image_id,
            filename=Path(file.filename).stem,
            path=str(image_path),
            status="pending",
            created_at= datetime.now(timezone.utc),
        )
        await self.uploaded_repo.create(uploaded)
        self.uploaded_images[uploaded.id] = uploaded

        # Async write to disk
        async with aiofiles.open(image_path, "wb") as out_file:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                await out_file.write(chunk)

        # Mark as uploaded
        uploaded.status = "uploaded"
        await self.uploaded_repo.update(uploaded)

        return uploaded

    # -------------------------------
    # Load uploaded image into Docker
    # -------------------------------
    async def load_new_image(self, uploaded_image_id: UUID) -> DockerImage:
        # Get uploaded image
        uploaded = await self.uploaded_repo.get(uploaded_image_id)
        if not uploaded:
            raise ValueError("Uploaded image not found")

        name = uploaded.filename
        tag = "latest"

        lock = self._locks[f"{name}:{tag}"]
        async with lock:
            # Load the image into Docker
            docker_id = await self.docker_runtime.load_image(uploaded.path)

            # Deactivate previous active images with the same name/tag
            docker_images = await self.docker_repo.list()
            for img in docker_images:
                if img.name == name and img.tag == tag and img.is_active:
                    img.is_active = False
                    await self.docker_repo.update(img)

            # Create the new DockerImage and mark as active
            docker_img = DockerImage(
                id=uuid4(),
                docker_id=docker_id,
                uploaded_image_id=uploaded.id,
                name=name,
                tag=tag,
                created_at= datetime.now(timezone.utc),
                is_active=True,
            )
            await self.docker_repo.create(docker_img)
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
    # List all Docker images
    # -------------------------------
    async def list_docker_images(self) -> List[DockerImage]:
        docker_images = await self.docker_repo.list()
        return docker_images

    # -------------------------------
    # Get single Docker image by ID
    # -------------------------------
    async def get_docker_image(self, image_id: UUID) -> DockerImage:
        docker_img = await self.docker_repo.get(image_id)
        if not docker_img:
            raise ValueError("Docker image not found")
        return docker_img
        

    async def load_or_activate_docker_image_uploaded(self, uploaded_image_id: UUID) -> DockerImage:
    # Get uploaded image
        uploaded = await self.get_uploaded_image(uploaded_image_id)

        lock = self._locks[str(uploaded.id)]
        async with lock:
            # Check for existing DockerImage
            docker_images = await self.list_docker_images()
            existing = next(
                (img for img in docker_images if img.uploaded_image_id == uploaded.id),
                None
            )

            if existing and existing.is_active:
                # Already loaded and active in Docker, nothing to do
                return existing

            # Load into Docker
            docker_id = await self.docker_runtime.load_image(uploaded.path)

            if existing:
                # Update existing record to be active
                existing.docker_id = docker_id
                existing.is_active = True
                existing.name = uploaded.filename
                existing.tag = "latest"
                await self.docker_repo.update(existing)
                await self._deactivate_other_images(existing.name, existing.tag, 
                                                    except_id=existing.id)
                return existing
            else:
                # Use your existing `load_new_image` function
                docker_img = await self.load_new_image(uploaded_image_id)
                return docker_img
            
    async def load_or_activate_docker_image_by_docker_id(self, docker_id: UUID) -> DockerImage:
        # Get uploaded image
        uploaded = await self.get_docker_image(docker_id)
        print(uploaded)
        return await self.load_or_activate_docker_image_uploaded(uploaded.uploaded_image_id)


    async def _deactivate_other_images(self, name: str, tag: str, except_id: UUID | None = None):
        """ 
        Set is_active = False for all DockerImages with the same name/tag,
        except the one with except_id.
        """
        docker_images = await self.docker_repo.list()
        print(docker_images)
        for img in docker_images:
            if img.name == name and img.tag == tag and img.is_active:
                if except_id is None or img.id != except_id:
                    img.is_active = False
                    await self.docker_repo.update(img)


    
