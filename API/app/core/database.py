# app/core/database.py
from databases import Database
from sqlalchemy import create_engine
from app.models.db import Base  # import your Base from models

DATABASE_URL = "sqlite+aiosqlite:///./app.db"
database = Database(DATABASE_URL)

# Create tables if they don't exist (synchronous)
engine = create_engine("sqlite:///./app.db", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)  # <- this creates uploaded_images, docker_images, containers
