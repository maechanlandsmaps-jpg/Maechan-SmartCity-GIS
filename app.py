from flask import Flask, render_template, request, jsonify
import psycopg2
from psycopg2 import errors
import json
import os

app = Flask(__name__)

# ดึงค่า URL จาก Render Environment
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        # สร้างตารางถ้ายังไม่มี
        c.execute('''CREATE TABLE IF NOT EXISTS features
                     (id SERIAL PRIMARY KEY, layer_name TEXT, properties TEXT, geojson TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS layers
                     (id SERIAL PRIMARY KEY, name TEXT UNIQUE, color TEXT, type TEXT, fields TEXT)''')
        conn.commit()
    except Exception as e:
        print(f"DB Init Error: {e}")
    finally:
        if conn: conn.close()

if DATABASE_URL:
    try: init_db()
    except: pass

@app.route('/')
def index():
    return render_template('index.html')

# --- API สำหรับ LAYERS ---
@app.route('/api/layers', methods=['GET'])
def get_layers():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, color, type, fields FROM layers")
    rows = c.fetchall()
    c.close()
    conn.close()
    return jsonify([{"id": r[0], "name": r[1], "color": r[2], "type": r[3], "fields": json.loads(r[4] if r[4] else '[]')} for r in rows])

@app.route('/api/layers', methods=['POST'])
def add_layer():
    data = request.json
    conn = get_db_connection()
    c = conn.cursor()
    try:
        fields_str = json.dumps([{"name": f["name"], "type": f["type"]} for f in data.get('fields', [])])
        c.execute("INSERT INTO layers (name, color, type, fields) VALUES (%s, %s, %s, %s)", 
                  (data['name'], data['color'], data['type'], fields_str))
        conn.commit()
        return jsonify({"status": "success"})
    except errors.UniqueViolation:
        conn.rollback()
        return jsonify({"status": "error_duplicate"})
    finally:
        c.close()
        conn.close()

# API ลบชั้นข้อมูล (ลบทั้งชั้นและพิกัดที่เกี่ยวข้อง)
@app.route('/api/layers/<name>', methods=['DELETE'])
def delete_layer(name):
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM features WHERE layer_name = %s", (name,))
        c.execute("DELETE FROM layers WHERE name = %s", (name,))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"status": "error", "message": str(e)})
    finally:
        if conn: conn.close()

# --- API สำหรับ FEATURES ---
@app.route('/api/features', methods=['GET'])
def get_features():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, layer_name, properties, geojson FROM features")
    rows = c.fetchall()
    c.close()
    conn.close()
    features = []
    for row in rows:
        f = json.loads(row[3])
        f['properties'] = json.loads(row[2]) if row[2] else {}
        f['properties']['id'] = row[0]
        f['properties']['layer_name'] = row[1]
        features.append(f)
    return jsonify({"type": "FeatureCollection", "features": features})

@app.route('/api/features', methods=['POST'])
def save_feature():
    data = request.json
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO features (layer_name, properties, geojson) VALUES (%s, %s, %s)", 
              (data.get('layer_name'), json.dumps(data.get('properties', {})), json.dumps(data.get('geojson'))))
    conn.commit()
    c.close()
    conn.close()
    return jsonify({"status": "success"})

# API ลบพิกัดรายจุด
@app.route('/api/features/<int:id>', methods=['DELETE'])
def delete_feature(id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM features WHERE id = %s", (id,))
    conn.commit()
    c.close()
    conn.close()
    return jsonify({"status": "success"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
