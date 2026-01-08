from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Dict, List, Optional, DefaultDict
from pathlib import Path
from app.domain.image import UploadedImage, DockerImage
from app.domain.ports import UploadedImageRepository, DockerImageRepository, DockerRuntime
from app.core.config import Settings
import asyncio
import aiofiles


class _UploadedImages:
    """Internal helper for uploaded tarballs."""
    def __init__(self, repo: UploadedImageRepository, settings: Settings):
        self.repo = repo
        self.settings = settings
        self.settings.IMAGE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.uploaded_images: Dict[UUID, UploadedImage] = {}

    async def load_from_repo(self):
        uploaded_list = await self.repo.list()
        self.uploaded_images = {img.id: img for img in uploaded_list}
        return uploaded_list

    async def register_upload(self, file) -> UploadedImage:
        file.file.seek(0, 2)
        size_mb = file.file.tell() / (1024 * 1024)
        if size_mb > self.settings.MAX_IMAGE_SIZE_MB:
            raise ValueError(f"File too large ({size_mb:.2f} MB)")
        file.file.seek(0)

        image_id = uuid4()
        image_path = self.settings.IMAGE_STORAGE_DIR / f"{image_id}_{file.filename}"

        uploaded = UploadedImage(
            id=image_id,
            filename=Path(file.filename).stem,
            path=str(image_path),
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        await self.repo.create(uploaded)
        self.uploaded_images[uploaded.id] = uploaded

        # Async write to disk
        async with aiofiles.open(image_path, "wb") as out_file:
            while chunk := await file.read(1024 * 1024):
                await out_file.write(chunk)

        uploaded.status = "uploaded"
        await self.repo.update(uploaded)
        return uploaded

    async def list_uploaded_images(self, latest_only: bool = False) -> List[UploadedImage]:
        images = await self.repo.list()
        if latest_only:
            latest_map: Dict[str, UploadedImage] = {}
            for img in images:
                current = latest_map.get(img.filename)
                if not current or img.created_at > current.created_at:
                    latest_map[img.filename] = img
            return list(latest_map.values())
        return images

    async def get_uploaded_image(self, image_id: UUID) -> UploadedImage:
        img = await self.repo.get(image_id)
        if not img:
            raise ValueError("Uploaded image not found")
        return img

    async def get_uploaded_image_by_name(self, filename: str, latest: bool = True) -> Optional[UploadedImage]:
        images = [img for img in await self.repo.list() if img.filename == filename]
        if not images:
            return None
        return max(images, key=lambda x: x.created_at) if latest else images[0]

    async def delete_uploaded_image(self, uploaded: UploadedImage):
        try:
            path = Path(uploaded.path)
            if path.exists():
                path.unlink()
        except Exception as e:
            print(f"[DELETE FILE ERROR] {uploaded.id}: {e}")
        await self.repo.delete(uploaded.id)
        self.uploaded_images.pop(uploaded.id, None)


class _DockerImages:
    """Internal helper for Docker images."""
    def __init__(self, repo: DockerImageRepository, docker_runtime: DockerRuntime):
        self.repo = repo
        self.docker_runtime = docker_runtime
        self.docker_images: Dict[UUID, DockerImage] = {}
        self._locks: Dict[str, asyncio.Lock] = DefaultDict(asyncio.Lock)

    async def load_from_repo(self):
        docker_list = await self.repo.list()
        self.docker_images = {img.id: img for img in docker_list}
        return docker_list

    async def list_docker_images(self) -> List[DockerImage]:
        return await self.repo.list()

    async def get_docker_image(self, image_id: UUID) -> DockerImage:
        img = await self.repo.get(image_id)
        if not img:
            raise ValueError("Docker image not found")
        return img

    async def load_new_image(self, uploaded: UploadedImage) -> DockerImage:
        name, tag = uploaded.filename, "latest"
        lock = self._locks[f"{name}:{tag}"]
        async with lock:
            docker_id = await self.docker_runtime.load_image(uploaded.path)
            for img in await self.repo.list():
                if img.name == name and img.tag == tag and img.is_active:
                    img.is_active = False
                    await self.repo.update(img)
            docker_img = DockerImage(
                id=uuid4(),
                docker_id=docker_id,
                uploaded_image_id=uploaded.id,
                name=name,
                tag=tag,
                created_at=datetime.now(timezone.utc),
                is_active=True,
            )
            await self.repo.create(docker_img)
            self.docker_images[docker_img.id] = docker_img
            return docker_img

    async def load_or_activate_docker_image_uploaded(self, uploaded: UploadedImage) -> DockerImage:
        lock = self._locks[str(uploaded.id)]
        async with lock:
            existing = next(
                (img for img in await self.list_docker_images() if img.uploaded_image_id == uploaded.id),
                None
            )

            if existing and existing.is_active:
                return existing

            docker_id = await self.docker_runtime.load_image(uploaded.path)
            if existing:
                existing.docker_id = docker_id
                existing.is_active = True
                existing.name = uploaded.filename
                existing.tag = "latest"
                await self.repo.update(existing)
                await self._deactivate_other_images(existing.name, existing.tag, except_id=existing.id)
                return existing
            return await self.load_new_image(uploaded)

    async def load_or_activate_docker_image_by_docker_id(self, docker_id: UUID, get_uploaded):
        docker_img = await self.get_docker_image(docker_id)
        uploaded = await get_uploaded(docker_img.uploaded_image_id)
        return await self.load_or_activate_docker_image_uploaded(uploaded)

    async def _deactivate_other_images(self, name: str, tag: str, except_id: Optional[UUID] = None):
        for img in await self.repo.list():
            if img.name == name and img.tag == tag and img.is_active:
                if except_id is None or img.id != except_id:
                    img.is_active = False
                    await self.repo.update(img)

    async def delete_docker_image(self, docker_img: DockerImage):
        if docker_img.is_active and docker_img.docker_id:
            try:
                await self.docker_runtime.remove(docker_img.docker_id)
            except Exception as e:
                print(f"[DELETE DOCKER ERROR] {docker_img.id}: {e}")
        await self.repo.delete(docker_img.id)
        self.docker_images.pop(docker_img.id, None)


class ImageService:
    """Umbrella service that exposes all public methods for the API."""
    def __init__(self, uploaded_repo, docker_repo, docker_runtime, settings=None):
        self.settings = settings or Settings()
        self._uploads = _UploadedImages(uploaded_repo, self.settings)
        self._docker = _DockerImages(docker_repo, docker_runtime)

    # ------------------------------- Load caches -------------------------------
    async def load_from_repos(self):
        uploaded_list = await self._uploads.load_from_repo()
        docker_list = await self._docker.load_from_repo()
        print(f"[DB LOAD] {len(uploaded_list)} uploaded images, {len(docker_list)} Docker images loaded")

    # ------------------------------- Uploads -------------------------------
    async def register_upload(self, file):
        return await self._uploads.register_upload(file)

    async def list_uploaded_images(self, latest_only=False):
        return await self._uploads.list_uploaded_images(latest_only)

    async def get_uploaded_image(self, image_id):
        return await self._uploads.get_uploaded_image(image_id)

    async def get_uploaded_image_by_name(self, filename, latest=True):
        return await self._uploads.get_uploaded_image_by_name(filename, latest)

    async def delete_uploaded_image(self, uploaded_image_id: UUID):
        uploaded = await self.get_uploaded_image(uploaded_image_id)
        # Delete linked Docker images first
        for img in await self.list_docker_images():
            if img.uploaded_image_id == uploaded.id:
                await self.delete_docker_image(img.id)
        await self._uploads.delete_uploaded_image(uploaded)

    # ------------------------------- Docker -------------------------------
    async def list_docker_images(self):
        return await self._docker.list_docker_images()

    async def get_docker_image(self, image_id):
        return await self._docker.get_docker_image(image_id)

    async def load_new_image(self, uploaded_image_id: UUID):
        uploaded = await self.get_uploaded_image(uploaded_image_id)
        return await self._docker.load_new_image(uploaded)

    async def load_or_activate_docker_image_uploaded(self, uploaded_image_id: UUID):
        uploaded = await self.get_uploaded_image(uploaded_image_id)
        return await self._docker.load_or_activate_docker_image_uploaded(uploaded)

    async def load_or_activate_docker_image_by_docker_id(self, docker_id: UUID):
        return await self._docker.load_or_activate_docker_image_by_docker_id(
            docker_id, self.get_uploaded_image
        )

    async def delete_docker_image(self, docker_image_id: UUID):
        docker_img = await self.get_docker_image(docker_image_id)
        await self._docker.delete_docker_image(docker_img)
