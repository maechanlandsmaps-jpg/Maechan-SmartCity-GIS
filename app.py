from flask import Flask, render_template, request, jsonify
import psycopg2
from psycopg2 import errors
import json
import os

app = Flask(__name__)

# ดึง URL ของฐานข้อมูลคลาวด์จาก Render
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    # ปรับแต่งการเชื่อมต่อให้รองรับ Direct Connection
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # สร้างตาราง features
        c.execute('''CREATE TABLE IF NOT EXISTS features
                     (id SERIAL PRIMARY KEY,
                      layer_name TEXT,
                      properties TEXT,
                      geojson TEXT)''')
        
        # สร้างตาราง layers
        c.execute('''CREATE TABLE IF NOT EXISTS layers
                     (id SERIAL PRIMARY KEY,
                      name TEXT UNIQUE,
                      color TEXT,
                      type TEXT,
                      fields TEXT)''')
        
        conn.commit()
        print("Database Tables Checked/Created Successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise e
    finally:
        if conn:
            conn.close()

if DATABASE_URL:
    try:
        init_db()
    except:
        pass

@app.route('/fix-db')
def fix_db():
    try:
        init_db()
        return "<h1>สำเร็จ! ตารางถูกสร้างเรียบร้อยแล้ว</h1><a href='/'>กลับหน้าหลัก</a>"
    except Exception as e:
        return f"<h1>เกิดข้อผิดพลาด: {str(e)}</h1>"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/layers', methods=['GET'])
def get_layers():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, color, type, fields FROM layers")
    rows = c.fetchall()
    c.close()
    conn.close()
    layers = [{"id": r[0], "name": r[1], "color": r[2], "type": r[3], "fields": json.loads(r[4] if r[4] else '[]')} for r in rows]
    return jsonify(layers)

@app.route('/api/layers', methods=['POST'])
def add_layer():
    data = request.json
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        clean_fields = [{"name": f["name"], "type": f["type"]} for f in data.get('fields', [])]
        fields_str = json.dumps(clean_fields)
        c.execute("INSERT INTO layers (name, color, type, fields) VALUES (%s, %s, %s, %s)", 
                  (data['name'], data['color'], data['type'], fields_str))
        conn.commit()
        return jsonify({"status": "success"})
    except errors.UniqueViolation:
        if conn: conn.rollback()
        return jsonify({"status": "error_duplicate"})
    except Exception as e:
        if conn: conn.rollback()
        print(f"Post Layer Error: {e}")
        return jsonify({"status": "error", "message": str(e)})
    finally:
        if conn: conn.close()

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
        feature_data = json.loads(row[3])
        feature_data['properties'] = json.loads(row[2]) if row[2] else {}
        feature_data['properties']['id'] = row[0]
        feature_data['properties']['layer_name'] = row[1]
        features.append(feature_data)
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
