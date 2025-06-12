import os
import time
import csv
import jwt
import aiohttp
import logging
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from passlib.context import CryptContext
from typing import Optional

# Password hashing context (if needed elsewhere)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp"}

logger = logging.getLogger(__name__)


def allowed_file(filename: str) -> bool:
    """Check if the file has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def verify_token(credentials: HTTPAuthorizationCredentials, secret_key: str, algorithm: str):
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(credentials.credentials, secret_key, algorithms=[algorithm], options={"verify_exp": False})
        # Manual exp check
        if 'exp' in payload:
            if int(payload['exp']) < int(time.time()):
                raise HTTPException(status_code=401, detail="Token kadaluarsa")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token kadaluarsa")
    except Exception:
        raise HTTPException(status_code=401, detail="Token tidak valid atau kadaluarsa")


def get_daily_nutrition(gender, umur, umur_satuan, hamil, usia_kandungan, menyusui, umur_anak, csv_path=None):
    """
    Mengambil kebutuhan harian dari CSV berdasarkan data user.
    Jika hamil/menyusui, kebutuhan = kebutuhan dasar + tambahan hamil/menyusui.
    """
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), 'nutrition.csv')
    kebutuhan_dasar = None
    tambahan = None
    # 1. Cari kebutuhan dasar (berdasarkan gender/umur)
    if gender and umur is not None and umur_satuan:
        if umur_satuan == 'tahun':
            with open(csv_path, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    kategori_csv = row['Kategori'].strip().lower()
                    gender_norm = (gender or '').strip().lower()
                    if kategori_csv == gender_norm:
                        umur_csv = row['Umur'].strip()
                        if '-' in umur_csv:
                            parts = umur_csv.split('-')
                            try:
                                min_u = int(parts[0].strip())
                                max_u = int(parts[1].replace('+','').strip())
                                if min_u <= int(umur) <= max_u and row['Satuan'].lower() == 'tahun':
                                    kebutuhan_dasar = row
                                    break
                            except:
                                continue
                        elif umur_csv.replace('+','').isdigit():
                            min_u = int(umur_csv.replace('+','').strip())
                            if int(umur) >= min_u and row['Satuan'].lower() == 'tahun':
                                kebutuhan_dasar = row
                                break
        elif umur_satuan == 'bulan':
            with open(csv_path, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['Kategori'] == 'Bayi/Anak':
                        umur_range = row['Umur'].split('-')
                        if len(umur_range) == 2:
                            min_u = int(umur_range[0].strip())
                            max_u = int(umur_range[1].strip())
                            if min_u <= int(umur) <= max_u and row['Satuan'] == 'bulan':
                                kebutuhan_dasar = row
                                break
    # 2. Tambahan jika hamil
    if hamil and usia_kandungan:
        if usia_kandungan <= 3:
            trimester = '1'
        elif usia_kandungan <= 6:
            trimester = '2'
        else:
            trimester = '3'
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['Kategori'].lower().startswith('hamil') and row['Umur'] == trimester and row['Satuan'].lower() == 'trimester':
                    tambahan = row
                    break
    # 3. Tambahan jika menyusui
    elif menyusui and umur_anak is not None:
        if umur_anak <= 6:
            menyusui_periode = '1 - 6'
        else:
            menyusui_periode = '7 - 12'
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['Kategori'].lower().startswith('menyusui') and row['Umur'] == menyusui_periode and row['Satuan'].lower() == 'bulan':
                    tambahan = row
                    break
    # 4. Gabungkan kebutuhan dasar + tambahan (jika ada)
    if kebutuhan_dasar:
        kebutuhan_final = kebutuhan_dasar.copy()
        if tambahan:
            # Kolom gizi utama
            gizi_keys = [
                "Energi (kkal)", "Protein (g)", "Total Lemak (g)", "Karbohidrat (g)", "Serat (g)", "Gula (g)", "Garam (mg)"
            ]
            for key in gizi_keys:
                try:
                    dasar = float(str(kebutuhan_dasar.get(key,0)).replace(',','.'))
                except:
                    dasar = 0
                try:
                    add = float(str(tambahan.get(key,0)).replace(',','.'))
                except:
                    add = 0
                kebutuhan_final[key] = dasar + add
        return kebutuhan_final
    elif tambahan:
        return tambahan
    else:
        return None


# --- Utility untuk proxy ML API ---
async def proxy_ml_api(url: str, payload: dict):
    logger.info(f"[ML PROXY] POST {url}")
    logger.info(f"[ML PROXY] Payload: {payload}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    data = {"detail": "ML API response is not valid JSON"}
                logger.info(f"[ML PROXY] Status: {resp.status}, Response: {data}")
                if resp.status >= 400:
                    raise HTTPException(status_code=resp.status, detail=data.get("detail") or data)
                return data
    except Exception as e:
        logger.error(f"[ML PROXY] ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Gagal memanggil ML API: {str(e)}")
