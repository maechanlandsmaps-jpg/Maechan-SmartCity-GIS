from flask import Flask, render_template, request, jsonify
import sqlite3
import json
import os

app = Flask(__name__)
DB_FILE = 'gis_data_v4.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS features
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  layer_name TEXT,
                  properties TEXT,
                  geojson TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS layers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  color TEXT,
                  type TEXT,
                  fields TEXT)''')
    
    c.execute("SELECT count(*) FROM layers")
    if c.fetchone()[0] == 0:
        default_fields = '[{"name": "ชื่อ", "type": "Text"}, {"name": "รายละเอียด", "type": "Text"}]'
        c.execute("INSERT INTO layers (name, color, type, fields) VALUES ('ประปาทำแดง', '#3b82f6', 'Line', ?)", (default_fields,))
        c.execute("INSERT INTO layers (name, color, type, fields) VALUES ('เสาไฟฟ้า', '#eab308', 'Point', ?)", (default_fields,))
        
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/layers', methods=['GET'])
def get_layers():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, name, color, type, fields FROM layers")
    rows = c.fetchall()
    conn.close()
    layers = [{"id": r[0], "name": r[1], "color": r[2], "type": r[3], "fields": json.loads(r[4] if r[4] else '[]')} for r in rows]
    return jsonify(layers)

@app.route('/api/layers', methods=['POST'])
def add_layer():
    data = request.json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # ดึงเอาเฉพาะ name กับ type ตอนสร้างใหม่ (old_name ยังไม่มี)
    clean_fields = [{"name": f["name"], "type": f["type"]} for f in data.get('fields', [])]
    fields_str = json.dumps(clean_fields)
    try:
        c.execute("INSERT INTO layers (name, color, type, fields) VALUES (?, ?, ?, ?)", 
                  (data['name'], data['color'], data['type'], fields_str))
        conn.commit()
        status = "success"
    except sqlite3.IntegrityError:
        status = "error_duplicate"
    conn.close()
    return jsonify({"status": status})

@app.route('/api/layers/<int:layer_id>', methods=['PUT'])
def edit_layer(layer_id):
    data = request.json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name FROM layers WHERE id = ?", (layer_id,))
    row = c.fetchone()
    old_layer_name = row[0]
    
    new_layer_name = data['name']
    new_fields = data.get('fields', [])
    
    # 1. จัดการข้อมูลโครงสร้าง Layer (ลบ old_name ออกเพื่อไม่ให้รกฐานข้อมูล)
    clean_fields = [{"name": f["name"], "type": f["type"]} for f in new_fields]
    fields_str = json.dumps(clean_fields)

    try:
        c.execute("UPDATE layers SET name=?, color=?, type=?, fields=? WHERE id=?", 
                  (new_layer_name, data['color'], data['type'], fields_str, layer_id))
        
        # 2. ตรวจสอบว่ามีการเปลี่ยนชื่อฟิลด์บ้างไหม? (Mapping old_key -> new_key)
        field_mapping = {}
        for f in new_fields:
            old_k = f.get('old_name')
            new_k = f.get('name')
            if old_k and new_k and old_k != new_k:
                field_mapping[old_k] = new_k

        # 3. อัปเดตตาราง Features (พิกัด) ทั้งหมดใน Layer นี้ ให้สอดคล้องกัน
        if old_layer_name != new_layer_name or len(field_mapping) > 0:
            c.execute("SELECT id, properties, geojson FROM features WHERE layer_name=?", (old_layer_name,))
            layer_features = c.fetchall()

            for feat_id, props_str, geojson_str in layer_features:
                # แปลงคุณสมบัติ (Properties) เดิม
                try:
                    props = json.loads(props_str) if props_str else {}
                except:
                    props = {}

                new_props = {}
                for k, v in props.items():
                    if k in field_mapping:
                        new_props[field_mapping[k]] = v # ถ้าเปลี่ยนชื่อ ให้ใช้คีย์ใหม่แทน
                    else:
                        new_props[k] = v

                # แปลง GeoJSON ที่ซ้อนอยู่ด้านในด้วย
                try:
                    geo_obj = json.loads(geojson_str) if geojson_str else {}
                    if 'properties' in geo_obj:
                        new_geo_props = {}
                        for k, v in geo_obj['properties'].items():
                            if k in field_mapping:
                                new_geo_props[field_mapping[k]] = v
                            else:
                                new_geo_props[k] = v
                        geo_obj['properties'] = new_geo_props
                    geojson_str = json.dumps(geo_obj)
                except:
                    pass

                # เซฟกลับลงฐานข้อมูล
                c.execute("UPDATE features SET layer_name=?, properties=?, geojson=? WHERE id=?", 
                          (new_layer_name, json.dumps(new_props), geojson_str, feat_id))

        conn.commit()
        status = "success"
    except sqlite3.IntegrityError:
        status = "error_duplicate"
    except Exception as e:
        print("Error Update:", e)
        status = "error"
        
    conn.close()
    return jsonify({"status": status})

@app.route('/api/layers/<int:layer_id>', methods=['DELETE'])
def delete_layer(layer_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name FROM layers WHERE id = ?", (layer_id,))
    row = c.fetchone()
    if row:
        layer_name = row[0]
        c.execute("DELETE FROM features WHERE layer_name = ?", (layer_name,))
        c.execute("DELETE FROM layers WHERE id = ?", (layer_id,))
        conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/features', methods=['GET'])
def get_features():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, layer_name, properties, geojson FROM features")
    rows = c.fetchall()
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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO features (layer_name, properties, geojson) VALUES (?, ?, ?)", 
              (data.get('layer_name'), json.dumps(data.get('properties', {})), json.dumps(data.get('geojson'))))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/features/<int:feature_id>', methods=['DELETE'])
def delete_feature(feature_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM features WHERE id = ?", (feature_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/import', methods=['POST'])
def import_features():
    data = request.json
    if not data or 'features' not in data:
        return jsonify({"status": "error", "message": "รูปแบบไฟล์ GeoJSON ไม่ถูกต้อง"})
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    layers_data = {}
    for feature in data['features']:
        props = feature.get('properties', {})
        layer_name = props.get('layer_name', 'นำเข้าใหม่')
        
        if layer_name not in layers_data:
            layers_data[layer_name] = {'features': [], 'keys': set()}
            
        layers_data[layer_name]['features'].append(feature)
        
        for key in props.keys():
            if key not in ['layer_name', 'id'] and not str(key).startswith('styleUrl'):
                layers_data[layer_name]['keys'].add(key)

    for layer_name, l_data in layers_data.items():
        c.execute("SELECT id, fields FROM layers WHERE name = ?", (layer_name,))
        row = c.fetchone()
        
        if not row:
            fields_schema = [{"name": k, "type": "Text"} for k in l_data['keys']]
            geo_type = 'Point'
            if len(l_data['features']) > 0:
                sample_type = l_data['features'][0].get('geometry', {}).get('type', '')
                if 'Line' in sample_type or 'Polygon' in sample_type:
                    geo_type = 'Line'
                    
            c.execute("INSERT INTO layers (name, color, type, fields) VALUES (?, ?, ?, ?)",
                      (layer_name, '#94a3b8', geo_type, json.dumps(fields_schema)))
        else:
            layer_id = row[0]
            try:
                existing_fields = json.loads(row[1]) if row[1] else []
            except:
                existing_fields = []
            
            existing_keys = [f['name'] for f in existing_fields]
            for k in l_data['keys']:
                if k not in existing_keys:
                    existing_fields.append({"name": k, "type": "Text"})
            
            c.execute("UPDATE layers SET fields = ? WHERE id = ?", (json.dumps(existing_fields), layer_id))
        
        for feature in l_data['features']:
            props = feature.get('properties', {})
            c.execute("INSERT INTO features (layer_name, properties, geojson) VALUES (?, ?, ?)",
                      (layer_name, json.dumps(props), json.dumps(feature)))
            
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)