from fastapi import APIRouter, status, Query, BackgroundTasks, HTTPException
from uuid import UUID
from typing import List
import asyncio
from app.services.container_service import ContainerService
from app.services.image_service import ImageService
from app.schemas.container import (
    ContainerCreateRequest,
    ContainerResponse,
)

container_service = ContainerService()
image_service = ImageService()
    


router = APIRouter(prefix="/containers", tags=["containers"])



@router.post("", response_model=ContainerResponse, status_code=202)
async def create_container(
    payload: ContainerCreateRequest,
    background_tasks: BackgroundTasks,
):
    container = await container_service.create_container(
        image=payload.image,
        cpu_limit=payload.cpu_limit,
        memory_limit_mb=payload.memory_limit_mb,
        internal_port=payload.internal_port,
    )

    background_tasks.add_task(container_service.deploy_container, container.id)
    return container


@router.post("/run_from_image", summary="Run a container from a loaded Docker image")
async def run_container_from_image(
    image_id: UUID = Query(..., description="UUID of a loaded Docker image"),
    internal_port: int = Query(80, description="Internal container port"),
    host_port: int | None = Query(None, description="Host port to bind (optional)"),
):
    try:
        container = await container_service.run_from_image(
            docker_image_id=image_id,
            internal_port=internal_port,
            host_port=host_port,
        )

        return {
            "id": container.id,
            "image": container.image,
            "status": container.status,
            "docker_id": container.docker_id,
            "internal_port": container.internal_port,
            "exposed_port": container.exposed_port,
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=list[ContainerResponse])
async def list_containers():
    return await container_service.list_containers()


@router.get("/{container_id}", response_model=ContainerResponse)
async def get_container(container_id: UUID):
    return await container_service.get_container(container_id)


@router.post("/{container_id}/stop", response_model=ContainerResponse)
async def stop_container(container_id: UUID):
    return await container_service.stop_container(container_id)


@router.delete("/{container_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_container(container_id: UUID):
    await container_service.delete_container(container_id)
    