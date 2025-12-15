# DSSI-68 – ระบบเว็บเช่าชุดออนไลน์ (Dress Rental System)

โปรเจกต์นี้เป็นระบบเว็บเช่าชุดออนไลน์แบบครบวงจร  
รองรับทั้งฝั่งผู้ใช้งานทั่วไป (ลูกค้า) และฝั่งผู้ดูแลร้านค้า (Back-Office)  
พัฒนาขึ้นเพื่อใช้เป็นโปรเจกต์รายวิชา DSSI-68

---

## ฟีเจอร์หลักของระบบ

- ระบบจัดการร้านค้า (Back-Office)
- ระบบเช่าชุด / คำนวณราคา / ตะกร้าสินค้า
- ระบบรีวิวชุดและร้านค้า
- ระบบโปรไฟล์ร้าน
- ระบบจัดการสถานะคำสั่งเช่า
- ระบบคำนวณสถิติหลังร้าน
- ระบบชำระเงิน
  - PromptPay (ผ่าน Omise)
  - Cash on Delivery
- AI ลองชุด

---

## เทคโนโลยีที่ใช้พัฒนา

- Python 3.x
- Django
- Database
  - SQLite (Development)
  - PostgreSQL (Production)
- HTML + TailwindCSS
- JavaScript

---

## System Architecture

- Backend: Django (Python)
- Frontend: Django Template + TailwindCSS + JavaScript
- Database: SQLite / PostgreSQL
- Payment Gateway: Omise (PromptPay)

---

## การติดตั้งและรันโปรเจกต์ (Setup & Run)

คู่มือนี้ใช้สำหรับการรันโปรเจกต์ในโหมดพัฒนา (Development Mode)

---

## 1) เตรียมเครื่องก่อนเริ่มต้น

โปรดติดตั้งเครื่องมือดังต่อไปนี้

- Python 3.x
- Git

ตรวจสอบเวอร์ชันที่ติดตั้งแล้ว

- python --version
- git --version


หมายเหตุ:  
บน macOS / Linux อาจต้องใช้คำสั่ง `python3`

---

## 2) Clone โปรเจกต์จาก GitHub

- git clone https://github.com/Tsaiwimon/DSSI-68-.git

- cd DSSI-68-


---

## 3) สร้าง Virtual Environment

### Windows
- python -m venv .venv
- .venv\Scripts\activate


### macOS / Linux
- python3 -m venv .venv
- source .venv/bin/activate


---

## 4) ติดตั้ง Dependencies
- pip install --upgrade pip
- pip install -r requirements.txt


---

## 5) การตั้งค่า Environment Variables (.env)

โปรเจกต์นี้ใช้ไฟล์ `.env` สำหรับเก็บค่า secret และ config ต่าง ๆ  
ไฟล์ `.env` จะไม่ถูกอัปขึ้น GitHub

### 5.1 สร้างไฟล์ `.env`
macOS / Linux
- cp .env.example .env
  
Windows
- copy .env.example .env


### 5.2 ตัวอย่างไฟล์ `.env`

- OMISE_PUBLIC_KEY=pkey_test_xxxxxxxxxxxxxxxxx
- OMISE_SECRET_KEY=skey_test_xxxxxxxxxxxxxxxxx
- OMISE_CURRENCY=thb


---

## 6) สร้างฐานข้อมูลและรัน Migrations

- python manage.py migrate


---

## 7) สร้าง Superuser (ผู้ดูแลระบบ)

- python manage.py createsuperuser

ข้อมูลที่ต้องกรอก
- Username
- Email (ไม่บังคับ)
- Password

ใช้สำหรับเข้าใช้งานหน้า Admin

---

## 8) รันเซิร์ฟเวอร์เพื่อพัฒนา

- python manage.py runserver


---

## 9) การเข้าใช้งานระบบหลังจากรัน

- หน้าเว็บหลัก  
  http://127.0.0.1:8000/

- หน้า Admin  
  http://127.0.0.1:8000/admin/

---

## Troubleshooting

### migrate ไม่ผ่าน
- ตรวจสอบว่า activate virtual environment แล้ว
- ตรวจสอบว่าไฟล์ `.env` ถูกสร้างแล้ว

### Port 8000 ถูกใช้งาน

- python manage.py runserver 8080


