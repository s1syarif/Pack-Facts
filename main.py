from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine
from routes import router  # import router dari routes.py
import os

app = FastAPI()

# Mount folder images sebagai static files
IMAGES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'images'))
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables
Base.metadata.create_all(bind=engine)

# Include router yang berisi semua route
app.include_router(router)
