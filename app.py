from flask import Flask, render_template, request, jsonify
import os
from datetime import datetime

app = Flask(__name__)

# หน้าหลักระบบแผนที่ Maechan GIS
@app.route('/')
def index():
    return render_template('index.html')

# API รองรับการรับข้อมูล Features (POST /api/features) ที่พังบ่อยๆ
@app.route('/api/features', methods=['POST'])
def save_features():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "ไม่พบข้อมูลที่ส่งมาจากหน้าเว็บ"}), 400

        # ตรวจสอบโครงสร้างหลักของ GeoJSON
        features = data.get('features', [])
        if not isinstance(features, list):
            return jsonify({"status": "error", "message": "รูปแบบโครงสร้าง GeoJSON ไม่ถูกต้อง"}), 400

        cleaned_features = []
        
        for feature in features:
            # แก้ไขบั๊กหลัก: ตรวจสอบและตัดฟีเจอร์ที่เป็นค่าว่าง (Null Check) ทิ้งไป
            if feature is None:
                print("⚠️ พบฟีเจอร์ที่มีค่าเป็น None: ระบบทำการข้ามเพื่อป้องกัน Error")
                continue
                
            if not isinstance(feature, dict) or 'geometry' not in feature:
                continue

            # แก้ไขบั๊ก: 'NoneType' object does not support item assignment 
            # ป้องกันกรณีตัวฟีเจอร์มีพิกัด แต่แถวข้อมูลอาร์เรย์ properties ข้างในหลุดมาเป็น null/None
            if feature.get('properties') is None:
                feature['properties'] = {}

            try:
                # ตัวอย่างจุดที่โค้ดเดิมเคยพยายามเขียนทับลง properties แล้วพัง
                # สามารถเปลี่ยนฟิลด์เหล่านี้ให้ตรงกับตาราง Supabase ของคุณได้เลยครับ
                feature['properties']['created_at'] = datetime.utcnow().isoformat()
                
                # หากผ่านด่านตรวจสอบความสะอาดเรียบร้อย ให้เก็บลงลิสต์
                cleaned_features.append(feature)
                
            except TypeError as te:
                print(f"❌ Error กำหนดค่า Properties ตกหล่น: {te}")
                continue

        # ========================================================
        # 🔗 ส่วนสำหรับเชื่อมต่อกับฐานข้อมูล Supabase เดิมของคุณ 
        # (สามารถใส่คำสั่งหรืองัดฟังก์ชัน insert ของคุณมาวางครอบตรงนี้ได้เลย)
        # ตัวอย่าง: supabase.table('your_table').insert(cleaned_features).execute()
        # ========================================================
        
        print(f"✅ ประมวลผลเสร็จสิ้น: ล้างข้อมูลเสียออกแล้ว เหลือข้อมูลที่สมบูรณ์ {len(cleaned_features)} แถว")

        return jsonify({
            "status": "success", 
            "message": "บันทึกข้อมูลและกรองส่วนที่เสียหายเรียบร้อยแล้ว", 
            "count": len(cleaned_features)
        }), 200

    except Exception as e:
        print(f"💥 Server Critical Error: {str(e)}")
        return jsonify({"status": "error", "message": f"เกิดข้อผิดพลาดภายในระบบ: {str(e)}"}), 500

if __name__ == '__main__':
    # รันพอร์ตตาม Environment ของ Render 
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
