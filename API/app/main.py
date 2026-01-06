from fastapi import FastAPI
from app.api import containers
from app.api import images

from app.services.image_service import ImageService
from app.services.container_service import ContainerService
from app.core.database import database

from app.repositories.container_repository import SQLContainerRepository
from app.repositories.image_repository import SQLDockerImageRepository
from app.repositories.uploaded_image_repository import SQLUploadedImageRepository

from app.services.docker_runtime import DockerSDKRuntime
from fastapi.middleware.cors import CORSMiddleware

docker_runtime = DockerSDKRuntime()
container_service = ContainerService(SQLContainerRepository(), SQLDockerImageRepository(), docker_runtime)
image_service = ImageService(SQLUploadedImageRepository(), SQLDockerImageRepository(), docker_runtime)


app = FastAPI(title="Mini AWS – Control Plane")

origins = [
    "http://localhost:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # can also be ["*"] for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(containers.router)

app.include_router(images.router)
# Service instance


# ---------- Startup / Shutdown ----------

@app.on_event("startup")
async def startup_event():
    # Connect to DB
    await database.connect()
    # Load images and docker images from DB
    container_service.start_reconciliation_loop(interval=10.0)
    await image_service.load_from_repos()
    print("[STARTUP] ImageService initialized from DB")


@app.on_event("shutdown")
async def shutdown_event():
    await database.disconnect()
    print("[SHUTDOWN] Database disconnected")
