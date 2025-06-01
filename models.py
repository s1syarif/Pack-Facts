from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from database import Base
from datetime import datetime

class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(255), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    nutrition_json = Column(Text, nullable=True)  # simpan hasil OCR (JSON string)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nama = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    bb = Column(Integer, nullable=False)  # berat badan
    tinggi = Column(Integer, nullable=False)
    umur = Column(Integer, nullable=False)
    gender = Column(String(20), nullable=True)
    umur_satuan = Column(String(10), nullable=True)
    hamil = Column(Integer, nullable=True)  # 0/1
    usia_kandungan = Column(Integer, nullable=True)
    menyusui = Column(Integer, nullable=True)  # 0/1
    umur_anak = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    timezone = Column(String(40), nullable=True, default="Asia/Jakarta")
