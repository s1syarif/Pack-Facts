# routes/auth.py
# Pindahan dari auth_routes.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os
from models import User
from database import SessionLocal
from utils import verify_token

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.environ.get("SECRET_KEY", "secretkey123")
ALGORITHM = "HS256"
security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_token_dependency(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return verify_token(credentials, SECRET_KEY, ALGORITHM)

class RegisterRequest(BaseModel):
    nama: str
    email: EmailStr
    password: str
    bb: int
    tinggi: int
    gender: str | None = None
    umur: int
    umur_satuan: str | None = None
    hamil: bool = False
    usia_kandungan: int | None = None
    menyusui: bool = False
    umur_anak: int | None = None
    timezone: str = "Asia/Jakarta"

class UserProfileResponse(BaseModel):
    id: int
    nama: str
    email: EmailStr
    bb: int
    tinggi: int
    gender: str | None = None
    umur: int
    umur_satuan: str | None = None
    hamil: bool = False
    usia_kandungan: int | None = None
    menyusui: bool = False
    umur_anak: int | None = None
    timezone: str

@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    hashed_password = pwd_context.hash(req.password)
    user = User(
        nama=req.nama,
        email=req.email,
        password=hashed_password,
        bb=req.bb,
        tinggi=req.tinggi,
        gender=req.gender,
        umur=req.umur,
        umur_satuan=req.umur_satuan,
        hamil=1 if req.hamil else 0,
        usia_kandungan=req.usia_kandungan,
        menyusui=1 if req.menyusui else 0,
        umur_anak=req.umur_anak,
        timezone=req.timezone
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Registrasi berhasil"}

@router.post("/login")
def login(
    email: str = Body(...),
    password: str = Body(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not pwd_context.verify(password, user.password):
        raise HTTPException(status_code=401, detail="Email atau password salah")
    import time
    token_data = {
        "user_id": user.id,
        "nama": user.nama,
        "exp": int(time.time()) + 86400,
        "gender": user.gender,
        "umur": user.umur,
        "umur_satuan": user.umur_satuan,
        "hamil": bool(user.hamil) if user.hamil is not None else False,
        "usia_kandungan": user.usia_kandungan,
        "menyusui": bool(user.menyusui) if user.menyusui is not None else False,
        "umur_anak": user.umur_anak,
        "timezone": user.timezone or "Asia/Jakarta"
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return {"userId": user.id, "name": user.nama, "token": token}

@router.get("/me", response_model=UserProfileResponse)
def get_profile(credentials: HTTPAuthorizationCredentials = Depends(security), user_data: dict = Depends(verify_token_dependency), db: Session = Depends(get_db)):
    user_id = user_data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User tidak ditemukan di token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan di database")
    return {
        "id": user.id,
        "nama": user.nama,
        "email": user.email,
        "bb": user.bb,
        "tinggi": user.tinggi,
        "gender": user.gender,
        "umur": user.umur,
        "umur_satuan": user.umur_satuan,
        "hamil": bool(user.hamil) if user.hamil is not None else False,
        "usia_kandungan": user.usia_kandungan,
        "menyusui": bool(user.menyusui) if user.menyusui is not None else False,
        "umur_anak": user.umur_anak,
        "timezone": user.timezone
    }

@router.put("/me", response_model=UserProfileResponse)
def update_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_data: dict = Depends(verify_token_dependency),
    db: Session = Depends(get_db),
    nama: str = Body(None),
    bb: int = Body(None),
    tinggi: int = Body(None),
    gender: str = Body(None),
    umur: int = Body(None),
    umur_satuan: str = Body(None),
    hamil: bool = Body(None),
    usia_kandungan: int = Body(None),
    menyusui: bool = Body(None),
    umur_anak: int = Body(None),
    timezone: str = Body(None)
):
    user_id = user_data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User tidak ditemukan di token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan di database")
    if nama is not None:
        user.nama = nama
    if bb is not None:
        user.bb = bb
    if tinggi is not None:
        user.tinggi = tinggi
    if gender is not None:
        user.gender = gender
    if umur is not None:
        user.umur = umur
    if umur_satuan is not None:
        user.umur_satuan = umur_satuan
    if hamil is not None:
        user.hamil = 1 if hamil else 0
    if usia_kandungan is not None:
        user.usia_kandungan = usia_kandungan
    if menyusui is not None:
        user.menyusui = 1 if menyusui else 0
    if umur_anak is not None:
        user.umur_anak = umur_anak
    if timezone is not None:
        user.timezone = timezone
    db.commit()
    db.refresh(user)
    return {
        "message": "Profil berhasil diupdate",
        "id": user.id,
        "nama": user.nama,
        "email": user.email,
        "bb": user.bb,
        "tinggi": user.tinggi,
        "gender": user.gender,
        "umur": user.umur,
        "umur_satuan": user.umur_satuan,
        "hamil": bool(user.hamil) if user.hamil is not None else False,
        "usia_kandungan": user.usia_kandungan,
        "menyusui": bool(user.menyusui) if user.menyusui is not None else False,
        "umur_anak": user.umur_anak,
        "timezone": user.timezone
    }
