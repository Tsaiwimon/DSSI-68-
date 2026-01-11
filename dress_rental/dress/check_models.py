from google import genai
import os

# ⚠️ ใส่ API Key ของคุณตรงนี้แทน AIzaSy...
client = genai.Client(api_key="AIzaSyBhbpCWN5qU5MV_6B9xYR7IguxTn4aWtuM") 

print("กำลังตรวจสอบรายชื่อโมเดลที่ใช้ได้...")
try:
    models = client.models.list()
    for m in models:
        # แสดงเฉพาะโมเดลที่เกี่ยวกับ gemini หรือ imagen
        if "gemini" in m.name or "imagen" in m.name:
            print(f"✅ พบโมเดล: {m.name}")
except Exception as e:
    print(f"❌ เกิดข้อผิดพลาด: {e}")