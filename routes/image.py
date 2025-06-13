# routes/image.py
# Pindahan dari image_routes.py
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Body, Form
from sqlalchemy.orm import Session
from models import Image
from database import SessionLocal
import os, uuid, shutil
from datetime import datetime
import pytz
from utils import allowed_file, extract_main_nutrition, map_kebutuhan_gizi, compare_nutrition
import logging
from fastapi.responses import HTMLResponse, JSONResponse
import aiohttp
from fastapi.security import HTTPAuthorizationCredentials
from routes.auth import security, verify_token_dependency  # Ganti ke dependency yang benar
from routes.nutrition import get_daily_nutrition  # Import from routes.nutrition

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
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_data: dict = Depends(verify_token_dependency)
):
    if file is None:
        raise HTTPException(status_code=422, detail="File tidak ditemukan di form-data. Pastikan field bernama 'file'.")
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="File type not allowed")

    kebutuhan = get_daily_nutrition(
        user_data.get("gender"),
        user_data.get("umur"),
        user_data.get("umur_satuan"),
        user_data.get("hamil"),
        user_data.get("usia_kandungan"),
        user_data.get("menyusui"),
        user_data.get("umur_anak")
    )
    try:
        ext = os.path.splitext(file.filename)[1]
        unique_id = str(uuid.uuid4())
        unique_filename = f"{unique_id}{ext}"
        file_location = os.path.join(IMAGE_DIR, unique_filename)
        os.makedirs(IMAGE_DIR, exist_ok=True)
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        # Ambil timezone user, default ke Asia/Jakarta jika tidak ada
        user_timezone = user_data.get("timezone", "Asia/Jakarta")
        try:
            tz = pytz.timezone(user_timezone)
        except Exception:
            tz = pytz.timezone("Asia/Jakarta")
        now = datetime.now(tz)
        image = Image(
            filename=unique_filename,
            filepath=file_location,
            uploaded_at=now,
            user_id=user_data.get("user_id")
        )
        db.add(image)
        db.commit()
        db.refresh(image)
        # Panggil OCR API
        ocr_result = await call_ocr_api(file_location)
        csv_key_map = {
            "energi": "Energi (kkal)",
            "protein": "Protein (g)",
            "lemak total": "Total Lemak (g)",
            "karbohidrat": "Karbohidrat (g)",
            "serat": "Serat (g)",
            "gula": "Gula (g)",
            "garam": "Garam (mg)"
        }
        kandungan_gizi = extract_main_nutrition(ocr_result)
        kebutuhan_gizi = map_kebutuhan_gizi(kebutuhan, csv_key_map)
        comparison = compare_nutrition(kandungan_gizi, kebutuhan_gizi)
        import json
        image.nutrition_json = json.dumps(kandungan_gizi, ensure_ascii=False)
        db.commit()
        return JSONResponse(content={
            "message": "File uploaded successfully",
            "id": image.id,
            "filename": image.filename,
            "kandungan_gizi": kandungan_gizi,
            "kebutuhan_harian": kebutuhan_gizi,
            "perbandingan": comparison
        })
    except Exception as e:
        print(f"Error uploading file: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"File upload failed: {str(e)}"})

async def call_ocr_api(image_path: str):
    OCR_API_URL = "https://3d45-180-242-24-202.ngrok-free.app/ocr/"
    try:
        with open(image_path, "rb") as img_file:
            image_data = img_file.read()
        async with aiohttp.ClientSession() as session:
            form_data = aiohttp.FormData()
            form_data.add_field('file', image_data, filename='image.png', content_type='image/png')
            async with session.post(OCR_API_URL, data=form_data) as response:
                print(f"Status OCR API response: {response.status}")
                if response.status == 200:
                    result = await response.json()
                    return result["result"]
                else:
                    raise HTTPException(status_code=500, detail="OCR API error")
    except Exception as e:
        print(f"Error during OCR processing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")
    
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