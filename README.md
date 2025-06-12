# Backend FastAPI - Nutrition Tracking App

## Struktur Folder

```
backend/
    main.py              # Entry point FastAPI
    models.py            # SQLAlchemy models
    crud.py              # CRUD logic
    database.py          # DB connection
    utils.py             # Helper & ML proxy
    nutrition.csv        # Data kebutuhan gizi
    alembic.ini          # Alembic config (migrasi DB)
    alembic/             # Folder migrasi DB
    core/                # Config & security
    routes/              # Modular routers (auth, image, nutrition)
    images/              # Upload gambar
```

## Menjalankan Backend

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Jalankan migrasi database (jika pakai Alembic)**
   ```bash
   alembic upgrade head
   ```

3. **Jalankan server**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## Fitur Utama
- **Autentikasi & Profil**: Register, login, update profil (JWT)
- **Upload & Scan Gambar**: Upload makanan, OCR, simpan hasil gizi
- **Kebutuhan Gizi**: Hitung kebutuhan harian dari biodata
- **Rekomendasi & Health Score**: Proxy ke ML API
- **Scan History**: Riwayat upload & hasil gizi
- **Migrasi Database**: Alembic

## Konfigurasi Penting
- `.env` (opsional):
  - `SECRET_KEY`, `BASE_API_URL`, dll
- `alembic.ini`: Ubah `sqlalchemy.url` sesuai DB Anda

## Struktur Modular
- Semua endpoint di folder `routes/` (auth, image, nutrition)
- Helper di `utils.py`
- Konfigurasi di `core/`

## CORS
- Sudah diaktifkan agar frontend (misal React/Vue) bisa akses API

## Catatan
- Folder `images/` untuk file upload, jangan dihapus
- File/folder `alembic*` hanya untuk migrasi DB
- Untuk pengembangan, gunakan virtual environment

---

**By: Tim Nutrition App**
