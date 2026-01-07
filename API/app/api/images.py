# app/api/images.py
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from app.services.image_service import ImageService
from app.schemas.image import UploadedImageResponse, DockerImageResponse

from app.repositories.image_repository import SQLDockerImageRepository
from app.repositories.uploaded_image_repository import SQLUploadedImageRepository

from app.services.docker_runtime import DockerSDKRuntime

docker_runtime = DockerSDKRuntime()


image_service = ImageService(uploaded_repo=SQLUploadedImageRepository(),
                            docker_repo=SQLDockerImageRepository(),
                            docker_runtime=docker_runtime)



router = APIRouter(prefix="/images", tags=["images"])
# ---------------------------
# Upload a new Docker image
# ---------------------------
@router.post(
    "/upload",
    response_model=UploadedImageResponse,
    status_code=202,
    summary="Upload a Docker image",
    description="Upload a Docker image tarball (.tar) to be stored and used for container deployment."
)
async def upload_image(
    file: UploadFile = File(..., description="Docker image tarball file to upload (e.g., myimage.tar)"),
    background_tasks: BackgroundTasks = None
):
    if not file.filename.endswith(".tar"):
        raise HTTPException(status_code=400, detail="Only .tar files are allowed")

    uploaded_image = await image_service.register_upload(file)

    # Schedule background Docker load
    if background_tasks:
        background_tasks.add_task(image_service.load_new_image, uploaded_image.id)
    
    # Although we have ORM i prefer not to.
    return UploadedImageResponse(
        id=uploaded_image.id,
        filename=uploaded_image.filename,
        status=uploaded_image.status
    )


# ---------------------------
# List all uploaded images
# ---------------------------
@router.get("/uploaded", response_model=list[UploadedImageResponse])
async def list_uploaded_images():
    uploaded_images = await image_service.list_uploaded_images()
    return [
        UploadedImageResponse(
            id=img.id,
            filename=img.filename,
            status=img.status
        )
        for img in uploaded_images
    ]


# ---------------------------
# List all Docker-loaded images
# ---------------------------
@router.get("/docker", response_model=list[DockerImageResponse])
async def list_docker_images():
    docker_images = await image_service.list_docker_images()
    return [
        DockerImageResponse(
            id=img.id,
            uploaded_image_id = img.uploaded_image_id,
            name=img.name,
            tag=img.tag,
            docker_id=img.docker_id,
            is_active=img.is_active
        )
        for img in docker_images
    ]


# ---------------------------
# Get single uploaded image
# ---------------------------
@router.get("/uploaded/{image_id}", response_model=UploadedImageResponse)
async def get_uploaded_image(image_id: UUID):
    try:
        img = await image_service.get_uploaded_image(image_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Uploaded image not found")

    return UploadedImageResponse(
        id=img.id,
        filename=img.filename,
        status=img.status
    )


# ---------------------------
# Get single Docker-loaded image
# ---------------------------
@router.get("/docker/{image_id}", response_model=DockerImageResponse)
async def get_docker_image(image_id: UUID):
    try:
        img = await image_service.get_docker_image(image_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Docker image not found")

    return DockerImageResponse(
        id=img.id,
        uploaded_image_id = img.uploaded_image_id,
        name=img.name,
        tag=img.tag,
        docker_id=img.docker_id,
        is_active=img.is_active
    )



# ---------------------------
# Load uploaded image into Docker
# ---------------------------
@router.post(
    "/uploaded/{uploaded_img_id}/load",
    status_code=202,
    summary="Load uploaded image into Docker",
    description="Loads an already uploaded Docker image tarball into the Docker daemon. If the image is already loaded and active, it returns the existing Docker image."
)
async def load_uploaded_image(
    uploaded_img_id: UUID
):
    try:
        # Use the new idempotent service function
        docker_img = await image_service.load_or_activate_docker_image_uploaded(uploaded_img_id)
        return DockerImageResponse(
            id=docker_img.id,
            uploaded_image_id=docker_img.uploaded_image_id,
            name=docker_img.name,
            tag=docker_img.tag,
            docker_id=docker_img.docker_id,
            is_active=docker_img.is_active
        )

    except ValueError:
        raise HTTPException(status_code=404, detail="Uploaded image not found")


# ---------------------------
# Load uploaded image into Docker
# ---------------------------
@router.post(
    "/docker/{docker_id}/load",
    status_code=202,
    summary="Load uploaded image into Docker",
    description="Loads an already uploaded Docker image tarball into the Docker daemon. If the image is already loaded and active, it returns the existing Docker image."
)
async def load_docker_image(
    docker_id: UUID
):
    try:
        # Use the new idempotent service function
        docker_img = await image_service.load_or_activate_docker_image_by_docker_id(docker_id)
        return DockerImageResponse(
            id=docker_img.id,
            uploaded_image_id=docker_img.uploaded_image_id,
            name=docker_img.name,
            tag=docker_img.tag,
            docker_id=docker_img.docker_id,
            is_active=docker_img.is_active
        )

    except ValueError:
        raise HTTPException(status_code=404, detail="Uploaded image not found")


