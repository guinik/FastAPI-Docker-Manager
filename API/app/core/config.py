from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict

class Settings(BaseSettings):
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    STORAGE_DIR: Path = Field(
        default=Path("storage"),
        description="Base directory for all stored artifacts"
    )

    IMAGE_STORAGE_DIR: Path = Field(
        default=Path("storage/images"),
        description="Where uploaded Docker images are stored"
    )

    MAX_IMAGE_SIZE_MB: int = 1024  # safety

    model_config = ConfigDict(
        env_file=".env"
    )