from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Body, Header
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from models import Image, User
from database import SessionLocal
import os, shutil, asyncio
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
    try:
        WIB_ZONE = ZoneInfo('Asia/Jakarta')
    except Exception:
        try:
            import pytz
            WIB_ZONE = pytz.timezone('Asia/Jakarta')
        except Exception:
            WIB_ZONE = None
except ImportError:
    try:
        import pytz
        WIB_ZONE = pytz.timezone('Asia/Jakarta')
    except Exception:
        WIB_ZONE = None
import aiohttp
from passlib.context import CryptContext
import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import time
import csv
import uuid

router = APIRouter()

IMAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'images'))
os.makedirs(IMAGE_DIR, exist_ok=True)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "secretkey123"  # Ganti dengan secret key yang aman
ALGORITHM = "HS256"

security = HTTPBearer()

# Dependency database
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        # Cek exp (expired) manual
        if 'exp' in payload:
            if int(payload['exp']) < int(time.time()):
                raise HTTPException(status_code=401, detail="Token kadaluarsa")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token kadaluarsa")
    except Exception:
        raise HTTPException(status_code=401, detail="Token tidak valid atau kadaluarsa")

@router.post("/upload/")
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_data: dict = Depends(verify_token)
):
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
        # Generate unique filename
        ext = os.path.splitext(file.filename)[1]
        unique_id = str(uuid.uuid4())
        unique_filename = f"{unique_id}{ext}"
        file_location = os.path.join(IMAGE_DIR, unique_filename)
        # Pastikan folder images/ ada sebelum menyimpan file
        os.makedirs(IMAGE_DIR, exist_ok=True)
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        image = Image(
            filename=unique_filename,
            filepath=file_location,
            uploaded_at=datetime.utcnow(),
            user_id=user_data.get("user_id")
        )
        db.add(image)
        db.commit()
        db.refresh(image)

        # Panggil fungsi OCR yang juga bisa kamu pisah di modul lain
        ocr_result = await call_ocr_api(file_location)

        # Ambil hanya kandungan gizi utama dari hasil OCR (exclude kolom non-gizi)
        gizi_keys = [
            "energi", "protein", "lemak total", "karbohidrat", "serat", "gula", "garam"
        ]
        kandungan_gizi = {}
        for key in gizi_keys:
            val = ocr_result.get(key)
            if val is None and key == "lemak total":
                val = ocr_result.get("total lemak")
            if val is not None:
                kandungan_gizi[key] = val
        # Mapping key backend ke kolom CSV
        csv_key_map = {
            "energi": "Energi (kkal)",
            "protein": "Protein (g)",
            "lemak total": "Total Lemak (g)",
            "karbohidrat": "Karbohidrat (g)",
            "serat": "Serat (g)",
            "gula": "Gula (g)",
            "garam": "Garam (mg)"
        }
        # Debug: print kebutuhan yang ditemukan
        print('DEBUG kebutuhan:', kebutuhan)
        # Hanya ambil kebutuhan harian untuk key yang ada di mapping dan di CSV
        kebutuhan_gizi = {}
        if kebutuhan:
            for key, csv_key in csv_key_map.items():
                print(f'DEBUG key: {key}, csv_key: {csv_key}, val: {kebutuhan.get(csv_key)}')
                if csv_key in kebutuhan and kebutuhan[csv_key] not in (None, ''):
                    val_raw = str(kebutuhan[csv_key]).strip().replace(',', '.')
                    try:
                        val = float(val_raw)
                    except:
                        val = 0
                    kebutuhan_gizi[key] = val
        # Gabungkan semua kunci gizi dari hasil OCR dan kebutuhan harian
        all_keys = set(kandungan_gizi.keys()) | set(kebutuhan_gizi.keys())
        # Buat tabel perbandingan
        comparison = []
        for key in all_keys:
            label = key.replace('_', ' ').replace('total', 'Total').title()
            ocr_val = kandungan_gizi.get(key) or kandungan_gizi.get(key.replace('_', ' ')) or 0
            kebutuhan_val = kebutuhan_gizi.get(key) or kebutuhan_gizi.get(key.replace('_', ' ')) or 0
            try:
                ocr_val = float(ocr_val)
            except:
                ocr_val = 0
            try:
                kebutuhan_val = float(kebutuhan_val)
            except:
                kebutuhan_val = 0
            status = 'Aman'
            if kebutuhan_val and ocr_val > kebutuhan_val:
                status = 'Melebihi'
            comparison.append({
                'label': label,
                'hasil_ocr': ocr_val,
                'kebutuhan_harian': kebutuhan_val,
                'status': status
            })
        # Simpan hasil OCR ke database saja, tidak perlu file JSON
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

@router.get("/", response_class=HTMLResponse)
async def read_root(db: Session = Depends(get_db)):
    images = db.query(Image).order_by(Image.uploaded_at.desc()).all()
    if not images:
        return "<h2>Belum ada gambar yang diupload.</h2>"

    html = "<h2>Gambar-gambar yang telah diupload:</h2>"
    for img in images:
        filename = os.path.basename(img.filepath)
        html += f'<div><img src="/images/{filename}" width="300"><p>{filename}</p></div>'
    return html

@router.delete("/delete/{filename}")
async def delete_image(filename: str, db: Session = Depends(get_db)):
    image = db.query(Image).filter(Image.filename == filename).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    if os.path.isfile(image.filepath):
        await remove_file_async(image.filepath)

    db.delete(image)
    db.commit()

    return {"message": f"Image {filename} deleted successfully"}

async def remove_file_async(path: str):
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, os.remove, path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")

# Contoh stub call_ocr_api, kamu bisa pindah ke file lain juga
async def call_ocr_api(image_path: str):
    ocr_api_url = "http://127.0.0.1:9000/ocr/"  # OCR API berada di port 9000
    try:
        # Baca gambar dan kirim ke API OCR
        with open(image_path, "rb") as img_file:
            image_data = img_file.read()

        # Kirim file sebagai multipart/form-data
        async with aiohttp.ClientSession() as session:
            form_data = aiohttp.FormData()
            form_data.add_field('file', image_data, filename='image.png', content_type='image/png')

            async with session.post(ocr_api_url, data=form_data) as response:
                print(f"Status OCR API response: {response.status}")  # Log status respons dari API OCR
                if response.status == 200:
                    result = await response.json()
                    return result["result"]
                else:
                    raise HTTPException(status_code=500, detail="OCR API error")

    except Exception as e:
        # Log error di console backend untuk debugging
        print(f"Error during OCR processing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")

@router.post("/register")
def register(
    nama: str = Body(...),
    email: str = Body(...),
    password: str = Body(...),
    bb: int = Body(...),
    tinggi: int = Body(...),
    gender: str = Body(None),
    umur: int = Body(...),
    umur_satuan: str = Body(None),
    hamil: bool = Body(False),
    usia_kandungan: int = Body(None),
    menyusui: bool = Body(False),
    umur_anak: int = Body(None),
    timezone: str = Body("Asia/Jakarta"),
    db: Session = Depends(get_db)
):
    # Cek email sudah terdaftar
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    hashed_password = pwd_context.hash(password)
    user = User(
        nama=nama,
        email=email,
        password=hashed_password,
        bb=bb,
        tinggi=tinggi,
        gender=gender,
        umur=umur,
        umur_satuan=umur_satuan,
        hamil=1 if hamil else 0,
        usia_kandungan=usia_kandungan,
        menyusui=1 if menyusui else 0,
        umur_anak=umur_anak,
        timezone=timezone
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
    # Generate token dengan seluruh biodata user
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

@router.get("/daily-nutrition")
async def get_daily_nutrition_endpoint(credentials: HTTPAuthorizationCredentials = Depends(security), user_data: dict = Depends(verify_token)):
    print("DEBUG user_data:", user_data)
    kebutuhan = get_daily_nutrition(
        user_data.get("gender"),
        user_data.get("umur"),
        user_data.get("umur_satuan"),
        user_data.get("hamil"),
        user_data.get("usia_kandungan"),
        user_data.get("menyusui"),
        user_data.get("umur_anak")
    )
    print("DEBUG kebutuhan:", kebutuhan)
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
            print(f"DEBUG key: {key}, csv_key: {csv_key}, val: {kebutuhan.get(csv_key)}")
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

def get_daily_nutrition(gender, umur, umur_satuan, hamil, usia_kandungan, menyusui, umur_anak):
    """
    Mengambil kebutuhan harian dari CSV berdasarkan data user.
    Jika hamil/menyusui, kebutuhan = kebutuhan dasar + tambahan hamil/menyusui.
    """
    print('DEBUG PARAMS:', gender, umur, umur_satuan, hamil, usia_kandungan, menyusui, umur_anak)
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

@router.get("/scan-history")
async def scan_history(credentials: HTTPAuthorizationCredentials = Depends(security), user_data: dict = Depends(verify_token), db: Session = Depends(get_db)):
    user_id = user_data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User tidak ditemukan di token")
    # Filter hanya gambar yang diupload hari ini (zona waktu user)
    user_timezone = user_data.get("timezone") or "Asia/Jakarta"
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(user_timezone)
    except Exception:
        try:
            import pytz
            tz = pytz.timezone(user_timezone)
        except Exception:
            # fallback manual offset
            offset = 7
            if user_timezone == "Asia/Makassar":
                offset = 8
            elif user_timezone == "Asia/Jayapura":
                offset = 9
            tz = None
    if tz:
        today_tz = datetime.now(tz).date()
        start_tz = datetime.combine(today_tz, datetime.min.time(), tzinfo=tz)
        end_tz = datetime.combine(today_tz, datetime.max.time(), tzinfo=tz)
        start_utc = start_tz.astimezone(timezone.utc)
        end_utc = end_tz.astimezone(timezone.utc)
    else:
        today_tz = (datetime.utcnow() + timedelta(hours=offset)).date()
        start_utc = datetime.combine(today_tz, datetime.min.time()) - timedelta(hours=offset)
        end_utc = datetime.combine(today_tz, datetime.max.time()) - timedelta(hours=offset)
    images = db.query(Image).filter(
        Image.user_id == user_id,
        Image.uploaded_at >= start_utc,
        Image.uploaded_at <= end_utc
    ).order_by(Image.uploaded_at.desc()).all()
    history = []
    for img in images:
        kandungan_gizi = {}
        if img.nutrition_json:
            import json
            try:
                kandungan_gizi = json.loads(img.nutrition_json)
            except:
                kandungan_gizi = {}
        uploaded_at_wib = img.uploaded_at
        if uploaded_at_wib.tzinfo is None:
            uploaded_at_wib = uploaded_at_wib.replace(tzinfo=timezone.utc)
        if WIB_ZONE:
            uploaded_at_wib = uploaded_at_wib.astimezone(WIB_ZONE)
        else:
            uploaded_at_wib = uploaded_at_wib + timedelta(hours=7)
        history.append({
            "filename": img.filename,
            "uploaded_at": uploaded_at_wib.strftime("%Y-%m-%d %H:%M:%S"),
            "kandungan_gizi": kandungan_gizi
        })
    return {"history": history}

@router.get("/scan-history-all")
async def scan_history_all(credentials: HTTPAuthorizationCredentials = Depends(security), user_data: dict = Depends(verify_token), db: Session = Depends(get_db)):
    user_id = user_data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User tidak ditemukan di token")
    images = db.query(Image).filter(
        Image.user_id == user_id
    ).order_by(Image.uploaded_at.desc()).all()
    history = []
    for img in images:
        kandungan_gizi = {}
        if img.nutrition_json:
            import json
            try:
                kandungan_gizi = json.loads(img.nutrition_json)
            except:
                kandungan_gizi = {}
        uploaded_at_wib = img.uploaded_at
        if uploaded_at_wib.tzinfo is None:
            uploaded_at_wib = uploaded_at_wib.replace(tzinfo=timezone.utc)
        if WIB_ZONE:
            uploaded_at_wib = uploaded_at_wib.astimezone(WIB_ZONE)
        else:
            uploaded_at_wib = uploaded_at_wib + timedelta(hours=7)
        history.append({
            "filename": img.filename,
            "uploaded_at": uploaded_at_wib.strftime("%Y-%m-%d %H:%M:%S"),
            "kandungan_gizi": kandungan_gizi
        })
    return {"history": history}

#post/register -> in nama, email, pass, bb, tinggi, umur, -> out berhasil atau gagal //1

#post/login -> in email, pass -> out userId, name, token //1

#upload -> foto -> kandungan gizi yang sudah di ocr dalam bentuk json //31

# get/checknotif -> menampilkan batas harian aku bandingin -> 
# output nilai perbandingan batas hariannya dan nilai apakah melibihi atau aman, jika ada yang melebihi kirim yang melebihinya apa //3

#get/kalkulasi -> menampilakan kalkulasi harian pengguna dan melihatnya lebih apa dan jika ada penyakit kirim ke front end //6

#get/scanhistory -> input id pengguna -> ouput file, nama file dan datetime //7

# subs/ unsubscribe -> peringatan kemungkinan kena penyakit //8

#saran kesehatan = produk produk apa yang bagus dan sehat misal yang rendah gula atau rendah lemak //8
# artikel kesehatan = menegnai produk produk atau gaya hidup sehat //8

#9 selesai