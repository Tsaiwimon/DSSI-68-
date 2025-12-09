# DSSI-68-
ระบบเว็บเช่าชุดออนไลน์
ระบบเว็บเช่าชุดออนไลน์ (Dress Rental Platform)

โปรเจกต์นี้เป็นระบบเช่าชุดออนไลน์แบบครบวงจร ประกอบด้วยฟีเจอร์

ระบบจัดการร้านค้า (Back-Office)

ระบบเช่าชุด / คำนวณราคา / ตระกร้า

ระบบรีวิว

ระบบโปรไฟล์ร้าน

ระบบจัดการสถานะคำสั่งเช่า

ระบบคำนวณสถิติหลังร้าน

ระบบชำระเงิน (รองรับ PromptPay หรือ Cash on Delivery แล้วแต่ตั้งค่า)

พัฒนาโดยใช้

Python 3.x

Django

SQLite / PostgreSQL

HTML + TailwindCSS

JavaScript




1) การติดตั้งและรันโปรเจกต์ (Setup & Run)

คู่มือนี้ใช้สำหรับรันโปรเจกต์บนเครื่องเพื่อพัฒนา (Development Mode)

2) เตรียมเครื่องก่อนเริ่ม

โปรดติดตั้งเครื่องมือดังนี้

Python 3.x

Git

ตรวจสอบว่าเครื่องติดตั้งแล้ว:

python --version
git --version


หมายเหตุ: macOS / Linux บางเครื่องต้องใช้คำสั่ง python3

3) Clone โปรเจกต์จาก GitHub
git clone https://github.com/USERNAME/REPOSITORY.git
cd REPOSITORY


เปลี่ยน USERNAME/REPOSITORY ให้ตรงกับโปรเจกต์จริง

4) สร้าง Virtual Environment
Windows
python -m venv .venv
.venv\Scripts\activate

macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

5) ติดตั้ง Dependencies
pip install --upgrade pip
pip install -r requirements.txt

6) ตั้งค่าไฟล์ Environment (.env)

หากมีไฟล์ .env.example ให้คัดลอก:

cp .env.example .env


แล้วแก้ค่าต่าง ๆ เช่น

SECRET_KEY

ฐานข้อมูล (SQLite / PostgreSQL)

คีย์ของ Payment Gateway เช่น Omise

ค่า Config สำหรับระบบร้านค้าแต่ละส่วน

หากไม่มี ให้สร้างไฟล์ .env เองตามตัวอย่างที่โปรเจกต์กำหนด

7) สร้างฐานข้อมูลและรัน Migrations
python manage.py migrate


คำสั่งนี้จะสร้างตารางทั้งหมดในฐานข้อมูล

8) สร้าง Superuser (แอดมินระบบ)
python manage.py createsuperuser


ข้อมูลที่ต้องกรอก:

Username

Email (ไม่บังคับ)

Password

ใช้สำหรับเข้า /admin/ เพื่อจัดการข้อมูล

9) โหลดข้อมูลตัวอย่าง (ถ้ามี)

หากโปรเจกต์มีไฟล์ Fixture เช่น:

python manage.py loaddata sample_data.json

10) รันเซิร์ฟเวอร์เพื่อพัฒนา
python manage.py runserver
