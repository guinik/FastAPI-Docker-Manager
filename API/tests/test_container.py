# tests/test_services.py
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock

from app.services.container_service import ContainerService
from app.domain.container import Container


@pytest.mark.asyncio
async def test_create_container_runs_and_sets_status():
    # Mocks
    container_repo = AsyncMock()
    docker_image_repo = AsyncMock()
    docker_runtime = AsyncMock()

    # Service
    service = ContainerService(container_repo, docker_image_repo, docker_runtime)

    # Docker runtime returns fake id and port
    docker_runtime.run = AsyncMock(return_value=("fake-docker-id", 8080))

    container = await service.create_container(
        image="ubuntu:latest",
        internal_port=80,
        memory_limit_mb=64,
        auto_start=True
    )

    # Assertions
    assert container.docker_id == "fake-docker-id"
    assert container.exposed_port == 8080
    assert container.status == "running"

    container_repo.create.assert_awaited_once()
    docker_runtime.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_container_sets_status_stopped():
    container_repo = AsyncMock()
    docker_runtime = AsyncMock()
    docker_image_repo = AsyncMock()

    service = ContainerService(container_repo, docker_image_repo, docker_runtime)

    container = Container(
        id=uuid4(),
        docker_image_id=None,
        image="ubuntu",
        status="running",
        cpu_limit=0.1,
        memory_limit_mb=64,
        internal_port=80,
        docker_id="fake-docker-id",
        exposed_port=8080,
    )

    container_repo.get = AsyncMock(return_value=container)

    await service.stop_container(container.id)

    assert container.status == "stopped"
    docker_runtime.stop.assert_awaited_once_with("fake-docker-id")
    container_repo.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_container_sets_status_running():
    container_repo = AsyncMock()
    docker_runtime = AsyncMock()
    docker_image_repo = AsyncMock()

    service = ContainerService(container_repo, docker_image_repo, docker_runtime)

    container = Container(
        id=uuid4(),
        docker_image_id=None,
        image="ubuntu",
        status="stopped",
        cpu_limit=0.1,
        memory_limit_mb=64,
        internal_port=80,
        docker_id="fake-docker-id",
    )
    container_repo.get = AsyncMock(return_value=container)
    docker_runtime.start = AsyncMock(return_value=8080)

    updated_container = await service.start_container(container.id)

    assert updated_container.status == "running"
    assert updated_container.exposed_port == 8080

    docker_runtime.start.assert_awaited_once_with("fake-docker-id")
    container_repo.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconcile_running_containers_sets_failed_or_stopped():
    container_repo = AsyncMock()
    docker_runtime = AsyncMock()
    docker_image_repo = AsyncMock()

    service = ContainerService(container_repo, docker_image_repo, docker_runtime)

    running_container = Container(
        id=uuid4(),
        docker_image_id=None,
        image="ubuntu",
        status="running",
        cpu_limit=0.1,
        memory_limit_mb=64,
        internal_port=80,
        docker_id="fake-docker-id",
    )
    container_repo.list = AsyncMock(return_value=[running_container])

    # Docker container disappeared
    docker_runtime.get_status = AsyncMock(return_value=None)

    await service.reconcile_running_containers()

    assert running_container.status == "failed"
    container_repo.update.assert_awaited()
