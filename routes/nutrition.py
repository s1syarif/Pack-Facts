# routes/nutrition.py
# Pindahan dari nutrition_routes.py
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import datetime, date
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from database import SessionLocal
from models import Image
from utils import get_daily_nutrition, proxy_ml_api
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_token_dependency(credentials: HTTPAuthorizationCredentials = Depends(security)):
    from utils import verify_token
    SECRET_KEY = os.environ.get("SECRET_KEY", "secretkey123")
    ALGORITHM = "HS256"
    return verify_token(credentials, SECRET_KEY, ALGORITHM)

class RecommendationPayload(BaseModel):
    konsumsi: dict
    target_harian: dict

class ScanHistoryItem(BaseModel):
    filename: str
    uploaded_at: datetime
    kandungan_gizi: dict = {}

class ScanHistoryAllResponse(BaseModel):
    history: List[ScanHistoryItem]

@router.get("/daily-nutrition")
async def get_daily_nutrition_endpoint(credentials: HTTPAuthorizationCredentials = Depends(security), user_data: dict = Depends(verify_token_dependency)):
    kebutuhan = get_daily_nutrition(
        user_data.get("gender"),
        user_data.get("umur"),
        user_data.get("umur_satuan"),
        user_data.get("hamil"),
        user_data.get("usia_kandungan"),
        user_data.get("menyusui"),
        user_data.get("umur_anak")
    )
    csv_key_map = {
        "energi": "Energi (kkal)",
        "protein": "Protein (g)",
        "lemak total": "Total Lemak (g)",
        "karbohidrat": "Karbohidrat (g)",
        "serat": "Serat (g)",
        "gula": "Gula (g)",
        "garam": "Garam (mg)"
    }
    kebutuhan_gizi = {}
    if kebutuhan:
        for key, csv_key in csv_key_map.items():
            if csv_key in kebutuhan and kebutuhan[csv_key] not in (None, ''):
                val_raw = str(kebutuhan[csv_key]).strip().replace(',', '.')
                try:
                    val = float(val_raw)
                except:
                    val = 0
                kebutuhan_gizi[key] = val
    else:
        return {"error": "Kebutuhan harian tidak ditemukan untuk data user ini."}
    return {"kebutuhan_harian": kebutuhan_gizi}

@router.post("/recommendation")
async def recommendation_proxy(payload: RecommendationPayload):
    BASE_API_URL = os.environ.get("BASE_API_URL", "https://e71f-180-242-24-202.ngrok-free.app")
    ML_RECOMMEND_URL = f"{BASE_API_URL}/recommend"
    result = await proxy_ml_api(ML_RECOMMEND_URL, payload.dict())
    return JSONResponse(status_code=200, content=result)

@router.get("/scan-history-all", response_model=ScanHistoryAllResponse)
def get_scan_history_all(credentials: HTTPAuthorizationCredentials = Depends(security), user_data: dict = Depends(verify_token_dependency), db: Session = Depends(get_db)):
    user_id = user_data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User tidak ditemukan di token")
    images = db.query(Image).filter(Image.user_id == user_id).order_by(Image.uploaded_at.desc()).all()
    history = []
    for img in images:
        try:
            import json
            kandungan_gizi = json.loads(img.nutrition_json) if img.nutrition_json else {}
        except Exception:
            kandungan_gizi = {}
        history.append(ScanHistoryItem(
            filename=img.filename,
            uploaded_at=img.uploaded_at,
            kandungan_gizi=kandungan_gizi
        ))
    return {"history": history}

@router.get("/scan-history", response_model=ScanHistoryAllResponse)
def get_scan_history_today(credentials: HTTPAuthorizationCredentials = Depends(security), user_data: dict = Depends(verify_token_dependency), db: Session = Depends(get_db)):
    user_id = user_data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User tidak ditemukan di token")
    today = date.today()
    images = db.query(Image).filter(
        Image.user_id == user_id,
        Image.uploaded_at >= datetime.combine(today, datetime.min.time()),
        Image.uploaded_at <= datetime.combine(today, datetime.max.time())
    ).order_by(Image.uploaded_at.desc()).all()
    history = []
    for img in images:
        try:
            import json
            kandungan_gizi = json.loads(img.nutrition_json) if img.nutrition_json else {}
        except Exception:
            kandungan_gizi = {}
        history.append(ScanHistoryItem(
            filename=img.filename,
            uploaded_at=img.uploaded_at,
            kandungan_gizi=kandungan_gizi
        ))
    return {"history": history}

@router.post("/predict")
async def predict_dieses_proxy(request: Request):
    BASE_API_URL = os.environ.get("BASE_API_URL", "https://e71f-180-242-24-202.ngrok-free.app")
    ML_PREDICT_URL = f"{BASE_API_URL}/predict-dieses"
    payload = await request.json()
    result = await proxy_ml_api(ML_PREDICT_URL, payload)
    return JSONResponse(status_code=200, content=result)

@router.post("/health-scoring")
async def health_score_proxy(request: Request):
    BASE_API_URL = os.environ.get("BASE_API_URL", "https://e71f-180-242-24-202.ngrok-free.app")
    ML_HEALTH_SCORE_URL = f"{BASE_API_URL}/health-score"
    payload = await request.json()
    result = await proxy_ml_api(ML_HEALTH_SCORE_URL, payload)
    return JSONResponse(status_code=200, content=result)
