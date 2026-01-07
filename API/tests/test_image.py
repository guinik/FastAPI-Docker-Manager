# tests/test_services.py
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
from app.services.image_service import ImageService
from app.domain.image import UploadedImage
from app.core.config import Settings
import io

settings = Settings()


@pytest.mark.asyncio
async def test_image_service_load_image():
    uploaded_repo = AsyncMock()
    docker_repo = AsyncMock()
    docker_runtime = AsyncMock()

    # Settings mock with real IMAGE_STORAGE_DIRs
    service = ImageService(uploaded_repo, docker_repo, docker_runtime, settings)

    uploaded_id = uuid4()
    uploaded_image = UploadedImage(
        id=uploaded_id,
        filename="test.tar",
        path="/fake/path/test.tar",
        status="uploaded",
        created_at=None,
    )
    uploaded_repo.get = AsyncMock(return_value=uploaded_image)

    docker_runtime.load_image = AsyncMock(return_value="docker-id-123")
    docker_repo.create = AsyncMock(return_value=None)
    uploaded_repo.update = AsyncMock(return_value=None)

    docker_image = await service.load_new_image(uploaded_id)
    print(docker_image)

    # Assertions
    assert docker_image.docker_id == "docker-id-123"
    assert uploaded_image.status == "uploaded"

    uploaded_repo.get.assert_awaited_once_with(uploaded_id)
    docker_runtime.load_image.assert_awaited_once_with("/fake/path/test.tar")
    docker_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_upload_creates_uploaded_image(tmp_path):
    uploaded_repo = AsyncMock()
    docker_repo = AsyncMock()
    docker_runtime = AsyncMock()

    service = ImageService(uploaded_repo, docker_repo, docker_runtime, settings)

    class AsyncFileMock:
        def __init__(self, content: bytes, filename: str):
            self.filename = filename
            self.file = io.BytesIO(content) 
            self._io = self.file

        async def read(self, n=-1):
            return self._io.read(n)  # mimic async read

    file = AsyncFileMock(b"dummy content", "fake.tar")

    uploaded = await service.register_upload(file)

    # .stem is used in your service
    assert uploaded.filename == "fake"
    uploaded_repo.create.assert_awaited_once()