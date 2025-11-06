# app.py
import os, io, requests, psycopg2, traceback
from flask import Flask, request, jsonify
from PIL import Image

app = Flask(__name__)

DB_DSN = os.environ.get("DB_DSN")

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
        data = request.get_json(force=True) or {}
        row_id  = data.get("row_id")
        foto_url = data.get("foto_url")

        print("[predict-photo] payload:", data)

        if not row_id or not foto_url:
            return jsonify({"error": "row_id & foto_url required"}), 400

        # 1) Coba unduh gambar
        try:
            r = requests.get(foto_url, timeout=20)
            print("[download] status:", r.status_code, "len:", len(r.content))
            r.raise_for_status()
        except Exception as e:
            print("[download] error:", repr(e))
            return jsonify({"error": f"cannot download foto_url: {e}"}), 400

        # 2) Buka image
        try:
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception as e:
            print("[image] error:", repr(e))
            return jsonify({"error": f"invalid image content: {e}"}), 400

        # 3) Prediksi
        label = predict_damage(img)
        print("[predict] label:", label)

        # 4) Update DB
        try:
            conn = psycopg2.connect(DB_DSN)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    update smart.hasil_investigasi_trafo
                       set hasil_cek_foto = %s, updated_at = now()
                     where id = %s
                """, (label, row_id))
                print("[db] rowcount:", cur.rowcount)
            conn.close()
        except Exception as e:
            print("[db] error:", repr(e))
            return jsonify({"error": f"db error: {e}"}), 500

        return jsonify({"row_id": row_id, "hasil_cek_foto": label}), 200

    except Exception as e:
        print("[predict-photo] unexpected:", repr(e))
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
