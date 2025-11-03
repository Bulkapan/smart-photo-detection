import os, io, requests, psycopg2
from flask import Flask, request, jsonify
from PIL import Image

app = Flask(__name__)
DB_DSN = os.environ["DB_DSN"]   # set di dashboard hosting (Render/Railway/Fly)

def predict_damage(img: Image.Image) -> str:
      
    g = img.convert("L").resize((256, 256))
    mean_px = sum(g.getdata()) / (256 * 256)
    return "Rusak" if mean_px < 80 else "Baik"

@app.post("/predict-photo")
def predict_photo():
    data = request.get_json(force=True)
    row_id  = data.get("row_id")
    foto_url = data.get("foto_url")
    if not row_id or not foto_url:
        return jsonify({"error": "row_id & foto_url required"}), 400

    # unduh gambar
    r = requests.get(foto_url, timeout=20)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGB")

    label = predict_damage(img)

    # update Neon
    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("""
            update smart.hasil_investigasi_trafo
               set hasil_cek_foto = %s, updated_at = now()
             where id = %s
        """, (label, row_id))
    conn.close()

    return jsonify({"row_id": row_id, "hasil_cek_foto": label})
