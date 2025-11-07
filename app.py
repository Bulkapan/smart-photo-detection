# app.py
import os, io, requests, psycopg2, traceback
from flask import Flask, request, jsonify
from PIL import Image

app = Flask(__name__)

DB_DSN = os.environ.get("DB_DSN")
APPSHEET_KEY = os.environ.get("APPSHEET_ACCESS_KEY", "")

def predict_damage(img):
    g = img.convert("L").resize((256, 256))
    mean_px = sum(g.getdata()) / (256 * 256)
    return "Rusak" if mean_px < 80 else "Baik"

@app.get("/")
def health():
    return {"status": "ok"}, 200

@app.post("/predict-photo")
def predict_photo():
    try:
        # (A) verifikasi request dari AppSheet (opsional tapi disarankan)
        client_key = request.headers.get("ApplicationAccessKey", "")
        if APPSHEET_KEY and client_key != APPSHEET_KEY:
            return jsonify({"error": "unauthorized"}), 401

        data = request.get_json(force=True) or {}
        row_id  = data.get("row_id")
        foto_url = data.get("foto_url")

        if not row_id or not foto_url:
            return jsonify({"error": "row_id & foto_url required"}), 400

        # (B) Unduh gambar dari AppSheet (butuh header khusus)
        headers = {"ApplicationAccessKey": APPSHEET_KEY} if APPSHEET_KEY else {}
        r = requests.get(foto_url, headers=headers, timeout=25)
        r.raise_for_status()

        img = Image.open(io.BytesIO(r.content)).convert("RGB")

        # (C) Prediksi sederhana
        label = predict_damage(img)

        # (D) Update ke Neon
        conn = psycopg2.connect(DB_DSN)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("""
                update smart.hasil_investigasi_trafo
                   set hasil_cek_foto = %s, updated_at = now()
                 where id = %s
            """, (label, row_id))
        conn.close()

        return jsonify({"row_id": row_id, "hasil_cek_foto": label}), 200

    except Exception as e:
        print("[predict-photo] error:", repr(e))
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
