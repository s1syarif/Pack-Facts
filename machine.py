from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import easyocr
import numpy as np
from PIL import Image
import io
import re

app = FastAPI()
reader = easyocr.Reader(['id'], gpu=False)

@app.post("/ocr/")
async def ocr_from_image(file: UploadFile = File(...)):
    try:
        # Baca file gambar yang di-upload
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_np = np.array(image)

        # Jalankan OCR untuk membaca teks dari gambar
        results = reader.readtext(image_np)

        # Ambil teks dari hasil OCR
        texts = [text for (_, text, _) in results]
        # Gabungkan semua hasil OCR menjadi satu string
        ocr_text = " ".join(texts).lower()
        print("Teks hasil OCR:", texts)  # Print list hasil OCR ke terminal

        # Daftar label kandungan gizi yang ingin diambil (lebih fleksibel)
        labels = {
            "energi": ["energi", "energi total", "energy"],
            "protein": ["protein"],
            "lemak total": ["lemak total", "lemak", "total fat", "fat"],
            "karbohidrat": ["karbohidrat", "karbohidrat total", "karbo", "carbohydrate", "carbohydrate total"],
            "serat": ["serat", "fiber"],
            "gula": ["gula", "sugar"],
            "garam": ["garam", "garam (natrium)", "natrium", "sodium", "salt"]
        }
        # Inisialisasi hasil dengan default 0
        result = {k: 0 for k in labels}

        # Ekstrak nilai kandungan gizi dari teks OCR
        for i, line in enumerate(texts):
            l = line.lower()
            for key, keys in labels.items():
                for label in keys:
                    if label in l:
                        # Pengecualian: hindari baris yang tidak relevan
                        if key == "energi" and ("kebutuhan energi" in l or "akg" in l):
                            continue
                        if key == "lemak total" and ("jenuh" in l or "trans" in l):
                            continue
                        value = None
                        # Cari angka di baris label dan 2 baris setelahnya
                        for offset in range(0, 3):
                            idx = i + offset
                            if idx < len(texts):
                                target_line = texts[idx].lower()
                                # Pengecualian untuk lemak total: hindari baris "lemak jenuh"
                                if key == "lemak total" and ("jenuh" in target_line or "trans" in target_line):
                                    continue
                                match = re.search(r"([0-9]+[\.,]?[0-9]*)", target_line)
                                if match:
                                    value = match.group(1).replace(",", ".")
                                    break
                        if value is not None:
                            try:
                                value = float(value)
                            except:
                                pass
                            result[key] = value
        print("Hasil ekstraksi OCR:", result)  # Print ke terminal
        return JSONResponse(content={"result": result})
    except Exception as e:
        # Mengembalikan pesan error jika ada masalah
        return JSONResponse(status_code=500, content={"error": str(e)})
