# routes/image.py
# Pindahan dari image_routes.py
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Body, Form
from sqlalchemy.orm import Session
from models import Image
from database import SessionLocal
import os, uuid, shutil
from datetime import datetime
from utils import allowed_file
import logging
from fastapi.responses import HTMLResponse

router = APIRouter()

IMAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'images'))
IMAGES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../images'))
os.makedirs(IMAGE_DIR, exist_ok=True)
logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/upload/")
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: int = Form(...)
):
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="File type not allowed")
    ext = os.path.splitext(file.filename)[1]
    unique_id = str(uuid.uuid4())
    unique_filename = f"{unique_id}{ext}"
    file_location = os.path.join(IMAGE_DIR, unique_filename)
    os.makedirs(IMAGE_DIR, exist_ok=True)
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    image = Image(
        filename=unique_filename,
        filepath=file_location,
        uploaded_at=datetime.utcnow(),
        user_id=user_id
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return {"message": "File uploaded successfully", "id": image.id, "filename": image.filename}

@router.delete("/delete/{filename}")
async def delete_image(filename: str, db: Session = Depends(get_db)):
    image = db.query(Image).filter(Image.filename == filename).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if os.path.isfile(image.filepath):
        try:
            os.remove(image.filepath)
        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
    db.delete(image)
    db.commit()
    return {"message": f"Image {filename} deleted successfully"}

@router.get("/")
async def read_root(db: Session = Depends(get_db)):
    images = db.query(Image).order_by(Image.uploaded_at.desc()).all()
    if not images:
        return "<h2>Belum ada gambar yang diupload.</h2>"
    html = "<h2>Gambar-gambar yang telah diupload:</h2>"
    for img in images:
        filename = os.path.basename(img.filepath)
        html += f'<div><img src="/images/{filename}" width="300"><p>{filename}</p></div>'
    return html

@router.get("/gallery", response_class=None)
def gallery():
    files = [
        f for f in os.listdir(IMAGES_DIR)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
    ]
    html = "<h2>Gallery</h2>"
    for filename in files:
        url = f"/images/{filename}"
        html += f'<div style="display:inline-block;margin:8px;"><img src="{url}" width="200"><br>{filename}</div>'
    return HTMLResponse(content=html)