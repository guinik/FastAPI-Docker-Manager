# app/api/images.py
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from app.services.image_service import ImageService
from app.schemas.image import UploadedImageResponse, DockerImageResponse

from app.repositories.container_repository import SQLContainerRepository
from app.repositories.image_repository import SQLDockerImageRepository
from app.repositories.uploaded_image_repository import SQLUploadedImageRepository

from app.services.docker_runtime import DockerSDKRuntime

docker_runtime = DockerSDKRuntime()
image_service = ImageService(SQLUploadedImageRepository(), SQLDockerImageRepository(), docker_runtime)



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
        background_tasks.add_task(image_service.load_image, uploaded_image.id)
    
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
            status=img.status
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
        status=img.status
    )



# ---------------------------
# Load uploaded image into Docker
# ---------------------------
@router.post(
    "/uploaded/{image_id}/load",
    status_code=202,
    summary="Load uploaded image into Docker",
    description="Loads an already uploaded Docker image tarball into the Docker daemon."
)
async def load_uploaded_image(
    image_id: UUID,
    background_tasks: BackgroundTasks
):
    try:
        uploaded_image = await image_service.get_uploaded_image(image_id)

        if uploaded_image.status == "loaded":
            raise HTTPException(
                status_code=409,
                detail="Image is already loaded into Docker"
            )

        # Run load asynchronously
        background_tasks.add_task(image_service.load_image, image_id)

        return {
            "id": image_id,
            "status": "loading"
        }

    except ValueError:
        raise HTTPException(status_code=404, detail="Uploaded image not found")




