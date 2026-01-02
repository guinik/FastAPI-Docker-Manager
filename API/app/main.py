from fastapi import FastAPI
from app.api import containers
from app.api import images

from app.services.image_service import ImageService

from app.services.container_service import ContainerService
from app.core.database import database


app = FastAPI(title="Mini AWS – Control Plane")

app.include_router(containers.router)

app.include_router(images.router)
# Service instance
image_service = ImageService()


# ---------- Startup / Shutdown ----------

@app.on_event("startup")
async def startup_event():
    # Connect to DB
    await database.connect()

    # Load images and docker images from DB
    await image_service.load_from_db()
    print("[STARTUP] ImageService initialized from DB")


@app.on_event("shutdown")
async def shutdown_event():
    await database.disconnect()
    print("[SHUTDOWN] Database disconnected")