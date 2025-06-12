from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine
import os
from routes.auth import router as auth_router
from routes.image import router as image_router
from routes.nutrition import router as nutrition_router

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

# 1. Error Handling (Best Practice: di main.py, bukan di router)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail or "Terjadi kesalahan pada server."}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    import traceback
    print('UNHANDLED ERROR:', traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Silakan coba lagi nanti."}
    )

app.include_router(auth_router)
app.include_router(image_router)
app.include_router(nutrition_router)
