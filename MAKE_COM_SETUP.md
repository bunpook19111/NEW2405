# Make.com Flow สำหรับโพสต์รูป + ข้อความขึ้น Facebook Page

> สำคัญ: เวอร์ชันนี้ใช้วิธี **ส่งลิงก์รูป (`image_url`)** ไม่ใช่ `image_base64` แบบเดิมอีกแล้ว
> เพราะ base64 ทำให้ Make สร้างโพสต์เป็น "ข้อความล้วน" ไม่มีรูป

## สิ่งที่ webhook ส่งมาให้ Make (ฟิลด์ระดับบนสุด)

| ฟิลด์ | ความหมาย |
|---|---|
| `caption` | ข้อความโพสต์ (พร้อม hashtag และเส้นทางน้ำ) |
| `image_url` | **ลิงก์รูปสาธารณะ** เช่น `https://i.ibb.co/xxx/inburi.png` ← ใช้ตัวนี้แนบรูป |
| `image_filename` | ชื่อไฟล์รูป |
| `image_mime` | `image/png` |
| `risk_level`, `confidence`, `page_name` | ข้อมูลประกอบ |
| `report` | object รายงานฉบับเต็ม |

## ขั้นตอนตั้ง Scenario

1. **Module 1 — Webhooks > Custom webhook**
   - Copy URL ไปใส่ GitHub Secret ชื่อ `MAKE_WEBHOOK_URL`

2. **Module 2 — HTTP > Get a file**  *(โมดูลคั่นกลางที่ทำให้รูปขึ้นชัวร์)*
   - URL: เลือก `image_url` จาก output ของ Webhook
   - โมดูลนี้จะดาวน์โหลดรูป PNG มาเป็นไฟล์ binary

3. **Module 3 — Facebook Pages > Create a Photo Post**
   - Page: อินทร์บุรีรอดมั้ย
   - Caption / Message: `caption`
   - **Photo: เลือกไฟล์ที่ได้จาก Module 2 (HTTP > Get a file)** ← จุดที่คนมักลืม
   - (อย่าใช้ "Create a Post" เพราะโมดูลนั้นโพสต์ข้อความล้วน ไม่แนบรูป)

4. เปิด Scenario

## ตรวจสอบก่อนใช้งานจริง

- [ ] GitHub Secrets มี `IMGBB_API_KEY` (ค่าเริ่มต้น `IMAGE_HOST=imgbb`)
      ถ้าไม่มี → `image_url` จะว่าง → ระบบจะไม่ส่ง webhook และไม่มีรูป
- [ ] ใช้ `inburi_ai/graphics.py` ที่แก้ฟอนต์ไทยแล้ว (ไม่งั้นตัวอักษรเป็นกล่อง □)
- [ ] workflow มีขั้นตอน `apt-get install -y fonts-thai-tlwg libcairo2` ก่อนรัน

## โหมดทดสอบ

ช่วงแรกตั้ง `DRY_RUN=true` ใน GitHub Variables เพื่อทดสอบก่อนโพสต์จริง
เมื่อแน่ใจแล้วค่อยตั้ง `DRY_RUN=false`

## ทางเลือก: ใช้ลิงก์ตรง (ถ้าเวอร์ชัน Make รับ URL ได้)

ถ้าโมดูล Facebook ของคุณมีช่องรับ Photo เป็น URL ได้โดยตรง
สามารถข้าม Module 2 (HTTP) แล้วใส่ `image_url` ลงช่อง Photo ได้เลย
แต่วิธี HTTP > Get a file จะเสถียรกว่าและรองรับได้ทุกเวอร์ชัน
