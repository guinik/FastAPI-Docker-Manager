from uuid import UUID
from typing import List
from fastapi import APIRouter, status, Query
from app.services.container_service import ContainerService
from app.services.image_service import ImageService
from app.schemas.container import (
    ContainerCreateRequest,
    ContainerResponse,
)

container_service = ContainerService()
image_service = ImageService()
router = APIRouter(prefix="/containers", tags=["containers"])
@router.post("", 
             response_model=ContainerResponse, 
             status_code=status.HTTP_202_ACCEPTED)
async def create_container(payload: ContainerCreateRequest):
    return await container_service.create_container(
        image=payload.image,
        image_id=payload.image_id,
        cpu_limit=payload.cpu_limit,
        memory_limit_mb=payload.memory_limit_mb,
        internal_port=payload.internal_port,
        host_port=payload.host_port,
        auto_start=payload.auto_start,
    )

@router.get("", response_model=List[ContainerResponse])
async def list_containers():
    print(await container_service.list_containers())
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



@router.post("/{container_id}/start", response_model=ContainerResponse)
async def start_container_endpoint(container_id: UUID):
    return await container_service.start_container(container_id)