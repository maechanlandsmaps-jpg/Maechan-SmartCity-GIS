from flask import Flask, render_template, request, jsonify
import os
from datetime import datetime

app = Flask(__name__)

# หน้าหลักแสดงแผนที่
@app.route('/')
def index():
    return render_template('index.html')

# API สำหรับรับข้อมูล Layers/Features (จุดที่มีปัญหา)
@app.route('/api/features', methods=['POST'])
def save_features():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "ไม่พบข้อมูลที่ส่งมา"}), 400

        # ตรวจสอบว่าสิ่งที่ส่งมาเป็น FeatureCollection หรือไม่
        features = data.get('features', [])
        if not isinstance(features, list):
            return jsonify({"status": "error", "message": "รูปแบบข้อมูล GeoJSON ไม่ถูกต้อง"}), 400

        cleaned_features = []
        
        for feature in features:
            # แก้ไขบั๊กลบฟีเจอร์ที่เป็นค่าว่าง (Null Check)
            if feature is None:
                print("พบฟีเจอร์ที่เป็น None: ข้ามการทำงาน")
                continue
                
            # ตรวจสอบโครงสร้างพื้นฐานของ GeoJSON Feature
            if not isinstance(feature, dict) or 'geometry' not in feature:
                continue

            # แก้ไขบั๊ก 'NoneType' object does not support item assignment
            # ป้องกันกรณีที่ฟีเจอร์มีตัวตน แต่ช่อง 'properties' หลุดมาเป็น null/None
            if feature.get('properties') is None:
                feature['properties'] = {}

            try:
                # ตัวอย่างการกำหนดค่าเพิ่มเติมลงใน properties (จุดเสี่ยงที่เคยเกิด Error)
                # ตรงนี้สามารถเปลี่ยนเป็นฟิลด์ที่คุณใช้งานจริงได้เลยครับ
                feature['properties']['processed_at'] = datetime.utcnow().isoformat()
                
                # หากผ่านการตรวจสอบ ให้เก็บเข้าลิสต์ข้อมูลที่สะอาดแล้ว
                cleaned_features.append(feature)
                
            except TypeError as ce:
                print(f"เกิดข้อผิดพลาดในการกำหนดค่า Properties: {ce}")
                continue

        # --- ส่วนเชื่อมต่อฐานข้อมูล (Supabase / Postgres) ---
        # นำ cleaned_features ไปบันทึกลง Database ของคุณต่อตรงนี้ได้เลย
        print(f"ประมวลผลข้อมูลสำเร็จ ทั้งหมด {len(cleaned_features)} ฟีเจอร์")
        # --------------------------------------------------

        return jsonify({
            "status": "success", 
            "message": "บันทึกข้อมูลเรียบร้อยแล้ว", 
            "count": len(cleaned_features)
        }), 200

    except Exception as e:
        print(f"Error parsing feature: {str(e)}")
        return jsonify({"status": "error", "message": f"เกิดข้อผิดพลาดบนเซิร์ฟเวอร์: {str(e)}"}), 500

if __name__ == '__main__':
    # รันบนพอร์ตมาตรฐานของ Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
