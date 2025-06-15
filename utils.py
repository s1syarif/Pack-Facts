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
    """Verifikasi JWT token dan kembalikan payload. Tambahkan logging error detail."""
    try:
        payload = jwt.decode(credentials.credentials, secret_key, algorithms=[algorithm], options={"verify_exp": False})
        # Manual exp check
        if 'exp' in payload:
            if int(payload['exp']) < int(time.time()):
                logger.warning(f"Token kadaluarsa: exp={payload['exp']}, now={int(time.time())}")
                raise HTTPException(status_code=401, detail="Token kadaluarsa")
        return payload
    except jwt.ExpiredSignatureError as e:
        logger.error(f"ExpiredSignatureError: {str(e)}")
        raise HTTPException(status_code=401, detail="Token kadaluarsa")
    except Exception as e:
        logger.error(f"Token tidak valid: {str(e)}")
        raise HTTPException(status_code=401, detail="Token tidak valid atau kadaluarsa")


def get_daily_nutrition(gender, umur, umur_satuan, hamil, usia_kandungan, menyusui, umur_anak, csv_path=None):
    """
    Mengambil kebutuhan harian dari CSV berdasarkan data user.
    Jika hamil/menyusui, kebutuhan = kebutuhan dasar + tambahan hamil/menyusui.
    """
    logger.info(f"get_daily_nutrition params: gender={gender}, umur={umur}, umur_satuan={umur_satuan}, hamil={hamil}, usia_kandungan={usia_kandungan}, menyusui={menyusui}, umur_anak={umur_anak}")
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), 'nutrition.csv')
    kebutuhan_dasar = None
    tambahan = None
    # 1. Cari kebutuhan dasar (berdasarkan gender/umur)
    if gender and umur is not None and umur_satuan:
        logger.info(f"Cari kebutuhan dasar: gender={gender}, umur={umur}, umur_satuan={umur_satuan}")
        if umur_satuan == 'tahun':
            with open(csv_path, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    kategori_csv = row['Kategori'].strip().lower()
                    gender_norm = (gender or '').strip().lower()
                    if kategori_csv == gender_norm:
                        umur_csv = row['Umur'].strip()
                        logger.info(f"Cek row: {row}")
                        if '-' in umur_csv:
                            parts = umur_csv.split('-')
                            try:
                                min_u = int(parts[0].strip())
                                max_u = int(parts[1].replace('+','').strip())
                                if min_u <= int(umur) <= max_u and row['Satuan'].lower() == 'tahun':
                                    kebutuhan_dasar = row
                                    logger.info(f"Dapat kebutuhan_dasar: {row}")
                                    break
                            except Exception as e:
                                logger.warning(f"Error parsing umur_csv: {umur_csv}, error: {e}")
                                continue
                        elif umur_csv.replace('+','').isdigit():
                            min_u = int(umur_csv.replace('+','').strip())
                            if int(umur) >= min_u and row['Satuan'].lower() == 'tahun':
                                kebutuhan_dasar = row
                                logger.info(f"Dapat kebutuhan_dasar: {row}")
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
                                logger.info(f"Dapat kebutuhan_dasar bayi/anak: {row}")
                                break
    # 2. Tambahan jika hamil
    if hamil and usia_kandungan:
        logger.info(f"Cari tambahan hamil: usia_kandungan={usia_kandungan}")
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
                    logger.info(f"Dapat tambahan hamil: {row}")
                    break
    # 3. Tambahan jika menyusui
    elif menyusui and umur_anak is not None:
        logger.info(f"Cari tambahan menyusui: umur_anak={umur_anak}")
        if umur_anak <= 6:
            menyusui_periode = '1 - 6'
        else:
            menyusui_periode = '7 - 12'
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['Kategori'].lower().startswith('menyusui') and row['Umur'] == menyusui_periode and row['Satuan'].lower() == 'bulan':
                    tambahan = row
                    logger.info(f"Dapat tambahan menyusui: {row}")
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
        logger.info(f"Kebutuhan final: {kebutuhan_final}")
        return kebutuhan_final
    elif tambahan:
        logger.info(f"Kebutuhan hanya tambahan: {tambahan}")
        return tambahan
    else:
        logger.warning("Tidak ditemukan kebutuhan harian yang cocok dengan data user!")
        return None


def extract_main_nutrition(ocr_result):
    gizi_keys = ["energi", "protein", "lemak total", "karbohidrat", "serat", "gula", "garam"]
    kandungan_gizi = {}
    for key in gizi_keys:
        val = ocr_result.get(key)
        if val is None and key == "lemak total":
            val = ocr_result.get("total lemak")
        if val is not None:
            kandungan_gizi[key] = val
    return kandungan_gizi


def map_kebutuhan_gizi(kebutuhan, csv_key_map):
    kebutuhan_gizi = {}
    if kebutuhan:
        for key, csv_key in csv_key_map.items():
            val = kebutuhan.get(csv_key)
            if val not in (None, ''):
                try:
                    kebutuhan_gizi[key] = float(str(val).strip().replace(',', '.'))
                except Exception:
                    kebutuhan_gizi[key] = 0
    return kebutuhan_gizi


def compare_nutrition(kandungan_gizi, kebutuhan_gizi):
    all_keys = set(kandungan_gizi.keys()) | set(kebutuhan_gizi.keys())
    comparison = []
    for key in all_keys:
        label = key.replace('_', ' ').replace('total', 'Total').title()
        ocr_val = float(kandungan_gizi.get(key, 0))
        kebutuhan_val = float(kebutuhan_gizi.get(key, 0))
        status = 'Aman'
        if kebutuhan_val and ocr_val > kebutuhan_val:
            status = 'Melebihi'
        comparison.append({
            'label': label,
            'hasil_ocr': ocr_val,
            'kebutuhan_harian': kebutuhan_val,
            'status': status
        })
    return comparison


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
